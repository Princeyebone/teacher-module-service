from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from model import KnowledgeEmbedding, KnowledgeMetadata
from sqlalchemy import select, text
from typing import List, Optional
from pydantic import BaseModel, Field
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[  
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/retrieval", tags=["RAG Retrieval"])

# Constants
EXPECTED_EMBEDDING_DIMENSIONS = 1536
DEFAULT_MIN_SIMILARITY = 0.3

# Import embedding functions
try:
    from rag.embedding import generate_embedding_with_gemini
    EMBEDDING_AVAILABLE = True
    logger.info("✅ Gemini embedding model available for retrieval")
except ImportError as e:
    EMBEDDING_AVAILABLE = False
    logger.error(f"❌ Failed to import embedding functions: {e}")

class QueryRequest(BaseModel):
    query: str
    subject: Optional[str] = None
    pillar: Optional[str] = None
    class_level: Optional[str] = Field(default=None, description="Class/grade level filter")
    limit: Optional[int] = Field(default=5, ge=1, le=100)
    min_similarity: Optional[float] = Field(default=DEFAULT_MIN_SIMILARITY, ge=0.0, le=1.0)
    use_hybrid_search: Optional[bool] = Field(default=True, description="Combine vector search with keyword search")
    keyword_weight: Optional[float] = Field(default=0.3, ge=0.0, le=1.0, description="Weight for keyword matching (0-1)")

class RetrievalResult(BaseModel):
    chunk_text: str
    similarity: float
    knowledge_id: int
    subject: Optional[str] = None
    pillar: Optional[str] = None
    chunk_index: Optional[int] = None
    keyword_match_score: Optional[float] = None
    combined_score: Optional[float] = None


def calculate_keyword_score(query: str, chunk_text: str) -> float:
    """
    Calculate simple keyword-based relevance score using token overlap.
    No hardcoded terms - pure token matching.
    """
    query_lower = query.lower()
    chunk_lower = chunk_text.lower()
    
    # Split into tokens
    query_tokens = set(query_lower.split())
    chunk_tokens = set(chunk_lower.split())
    
    if not query_tokens:
        return 0.0
    
    # Calculate simple overlap
    intersection = query_tokens.intersection(chunk_tokens)
    overlap_score = len(intersection) / len(query_tokens)
    
    # Bonus for exact phrase match (entire query appears in chunk)
    phrase_bonus = 0.2 if query_lower in chunk_lower else 0.0
    
    return min(overlap_score + phrase_bonus, 1.0)


async def find_knowledge_documents(
    db: AsyncSession, 
    subject: Optional[str], 
    pillar: Optional[str], 
    class_level: Optional[str]
) -> Optional[List[int]]:
    """
    Find knowledge document IDs by filtering on metadata fields.
    Uses ILIKE for flexible case-insensitive matching.
    
    Returns:
        List of knowledge_ids if filters are provided, None otherwise
    """
    if not any([subject, pillar, class_level]):
        return None
    
    # Build dynamic WHERE clause
    where_conditions = []
    params = {}
    
    if subject:
        where_conditions.append("subject ILIKE :subject")
        params["subject"] = f"%{subject}%"
    
    if pillar:
        where_conditions.append("pillar ILIKE :pillar")
        params["pillar"] = f"%{pillar}%"
    
    if class_level:
        # Search in both 'level' field and 'notes' field for class level
        where_conditions.append("(level ILIKE :class_level OR notes ILIKE :class_level)")
        params["class_level"] = f"%{class_level}%"
    
    where_clause = " AND ".join(where_conditions)
    
    sql_query = text(f"""
        SELECT id, subject, pillar, level, notes
        FROM knowledgemetadata
        WHERE {where_clause}
    """)
    
    result = await db.execute(sql_query, params)
    rows = result.fetchall()
    
    if rows:
        knowledge_ids = [row.id for row in rows]
        logger.info(f"✅ Found {len(knowledge_ids)} documents matching filters: subject={subject}, pillar={pillar}, class_level={class_level}")
        logger.info(f"   Document IDs: {knowledge_ids}")
        return knowledge_ids
    else:
        logger.warning(f"❌ No documents found matching filters: subject={subject}, pillar={pillar}, class_level={class_level}")
        return []


@router.post("/search", summary="Search for relevant knowledge chunks", response_model=List[RetrievalResult])
async def search_knowledge(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search for relevant knowledge chunks using vector similarity search with optional hybrid search.
    
    Args:
        request: Query request containing the search query and optional filters
        db: Database session
        
    Returns:
        List of retrieval results with similarity scores
    """
    if not EMBEDDING_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding model not available"
        )
    
    try:
        logger.info(f"🔍 Starting retrieval for query: '{request.query}'")
        logger.info(f"   Filters - subject: {request.subject}, pillar: {request.pillar}, class: {request.class_level}")
        
        # Find relevant documents based on metadata filters
        knowledge_id_filters = await find_knowledge_documents(
            db, 
            request.subject, 
            request.pillar, 
            request.class_level
        )
        
        # If filters were provided but no documents found, return empty
        if knowledge_id_filters is not None and len(knowledge_id_filters) == 0:
            logger.warning(f"No documents match the provided filters")
            return []
        
        # Generate embedding for the query
        query_embedding = generate_embedding_with_gemini(request.query)
        
        if not query_embedding:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate query embedding"
            )
        
        # Validate embedding dimensions
        if len(query_embedding) != EXPECTED_EMBEDDING_DIMENSIONS:
            error_msg = f"Embedding dimension mismatch: expected {EXPECTED_EMBEDDING_DIMENSIONS}, got {len(query_embedding)}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )
        
        logger.info(f"✅ Generated query embedding with {len(query_embedding)} dimensions")
        
        # Convert query embedding to PostgreSQL array format
        query_embedding_array = "[" + ",".join(str(x) for x in query_embedding) + "]"
        
        # Build WHERE clause for vector search
        where_conditions = []
        params = {
            "query_embedding": query_embedding_array,
            "limit": request.limit * 3 if request.use_hybrid_search else request.limit
        }
        
        # Add knowledge_id filter if documents were found
        if knowledge_id_filters:
            placeholders = ",".join([f":kid_{i}" for i in range(len(knowledge_id_filters))])
            where_conditions.append(f"km.id IN ({placeholders})")
            for i, kid in enumerate(knowledge_id_filters):
                params[f"kid_{i}"] = kid
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Perform similarity search using cosine similarity with pgvector
        sql_query = text(f"""
            SELECT 
                ke.chunk_text,
                ke.knowledge_id,
                ke.chunk_order,
                km.subject,
                km.pillar,
                ke.embedding <=> :query_embedding AS cosine_distance
            FROM knowledgeembedding ke
            JOIN knowledgemetadata km ON ke.knowledge_id = km.id
            {where_clause}
            ORDER BY ke.embedding <=> :query_embedding
            LIMIT :limit
        """)
        
        # Execute the query with parameters
        result = await db.execute(sql_query, params)
        rows = result.fetchall()
        
        logger.info(f"📊 Found {len(rows)} results from database")
        
        # Process results
        all_results = []
        for row in rows:
            # Convert cosine distance to similarity
            cosine_distance = row.cosine_distance
            similarity = 1 - cosine_distance
            
            # Calculate keyword match score if hybrid search is enabled
            keyword_score = 0.0
            combined_score = similarity
            
            if request.use_hybrid_search:
                keyword_score = calculate_keyword_score(request.query, row.chunk_text)
                
                # Combine vector and keyword scores using the weight parameter
                vector_weight = 1 - request.keyword_weight
                combined_score = (vector_weight * similarity) + (request.keyword_weight * keyword_score)
            
            all_results.append({
                "chunk_text": row.chunk_text,
                "similarity": similarity,
                "knowledge_id": row.knowledge_id,
                "subject": row.subject,
                "pillar": row.pillar,
                "chunk_order": row.chunk_order,
                "keyword_score": keyword_score,
                "combined_score": combined_score
            })
        
        # Sort by combined score (or similarity if not using hybrid search)
        sort_key = "combined_score" if request.use_hybrid_search else "similarity"
        all_results.sort(key=lambda x: x[sort_key], reverse=True)
        
        # Apply limit after sorting (for hybrid search)
        if request.use_hybrid_search:
            all_results = all_results[:request.limit]
        
        # Apply minimum similarity threshold and format results
        final_results = []
        for result in all_results:
            if result["similarity"] >= request.min_similarity:
                final_results.append(RetrievalResult(
                    chunk_text=result["chunk_text"],
                    similarity=round(result["similarity"], 4),
                    knowledge_id=result["knowledge_id"],
                    subject=result["subject"],
                    pillar=result["pillar"],
                    chunk_index=result["chunk_order"],
                    keyword_match_score=round(result["keyword_score"], 4) if request.use_hybrid_search else None,
                    combined_score=round(result["combined_score"], 4) if request.use_hybrid_search else None
                ))
        
        logger.info(f"✅ Retrieved {len(final_results)} results above similarity threshold ({request.min_similarity})")
        
        if len(final_results) > 0:
            top_score = final_results[0].combined_score if request.use_hybrid_search else final_results[0].similarity
            logger.info(f"   Top result score: {top_score}")
        
        return final_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error during retrieval: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {str(e)}"
        )
