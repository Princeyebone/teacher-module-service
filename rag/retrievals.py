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
DEFAULT_MIN_SIMILARITY = 0.3  # Lowered from 0.5 for better recall

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
    class_level: Optional[str] = Field(default=None, description="Class/grade level (e.g., 'jhs1', 'basic 3', 'grade 5')")
    limit: Optional[int] = Field(default=5, ge=1, le=100)
    min_similarity: Optional[float] = Field(default=DEFAULT_MIN_SIMILARITY, ge=0.0, le=1.0)
    use_hybrid_search: Optional[bool] = Field(default=True, description="Combine vector search with keyword search")
    keyword_boost: Optional[float] = Field(default=1.0, ge=0.0, le=3.0, description="Multiplier for keyword scores (higher = more keyword weight)")
    context_window: Optional[int] = Field(default=0, ge=0, le=5, description="Include N chunks before/after each result")

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
    Calculate keyword-based relevance score using token overlap and exact phrase matching.
    Enhanced for educational/structured content queries with strict grade-level matching.
    """
    query_lower = query.lower()
    chunk_lower = chunk_text.lower()
    
    # Extract key terms from query
    query_tokens = set(query_lower.split())
    chunk_tokens = set(chunk_lower.split())
    
    # Define stopwords - expanded for better filtering
    stopwords = {'the', 'a', 'an', 'for', 'in', 'on', 'at', 'to', 'of', 'and', 'or', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
    
    # Keep important educational terms even if they might be common
    important_terms = {'strand', 'substrand', 'sub-strand', 'indicator', 'content', 'standard', 'objective', 
                       'jhs', 'jhs1', 'jhs2', 'jhs3', 'basic', 'grade', 'curriculum', 'syllabus'}
    
    query_tokens_filtered = (query_tokens - stopwords) | (query_tokens & important_terms)
    
    if not query_tokens_filtered:
        return 0.0
    
    # CRITICAL: Check for grade level match first - this is a hard filter
    grade_penalty = 0.0
    query_has_grade = False
    chunk_has_grade = False
    grades_match = False
    
    # Extract grade levels from query
    query_grades = set()
    if 'jhs1' in query_lower or 'jhs 1' in query_lower:
        query_grades.add('jhs1')
        query_has_grade = True
    if 'jhs2' in query_lower or 'jhs 2' in query_lower:
        query_grades.add('jhs2')
        query_has_grade = True
    if 'jhs3' in query_lower or 'jhs 3' in query_lower:
        query_grades.add('jhs3')
        query_has_grade = True
    if 'basic 1' in query_lower or 'b1' in query_lower or 'b1.' in query_lower:
        query_grades.add('b1')
        query_has_grade = True
    if 'basic 2' in query_lower or 'b2' in query_lower or 'b2.' in query_lower:
        query_grades.add('b2')
        query_has_grade = True
    if 'basic 3' in query_lower or 'b3' in query_lower or 'b3.' in query_lower:
        query_grades.add('b3')
        query_has_grade = True
    if 'basic 4' in query_lower or 'b4' in query_lower or 'b4.' in query_lower:
        query_grades.add('b4')
        query_has_grade = True
    if 'basic 5' in query_lower or 'b5' in query_lower or 'b5.' in query_lower:
        query_grades.add('b5')
        query_has_grade = True
    if 'basic 6' in query_lower or 'b6' in query_lower or 'b6.' in query_lower:
        query_grades.add('b6')
        query_has_grade = True
    
    # Extract grade levels from chunk
    chunk_grades = set()
    if 'jhs1' in chunk_lower or 'jhs 1' in chunk_lower:
        chunk_grades.add('jhs1')
        chunk_has_grade = True
    if 'jhs2' in chunk_lower or 'jhs 2' in chunk_lower:
        chunk_grades.add('jhs2')
        chunk_has_grade = True
    if 'jhs3' in chunk_lower or 'jhs 3' in chunk_lower:
        chunk_grades.add('jhs3')
        chunk_has_grade = True
    if 'b1.' in chunk_lower or 'basic 1' in chunk_lower:
        chunk_grades.add('b1')
        chunk_has_grade = True
    if 'b2.' in chunk_lower or 'basic 2' in chunk_lower:
        chunk_grades.add('b2')
        chunk_has_grade = True
    if 'b3.' in chunk_lower or 'basic 3' in chunk_lower:
        chunk_grades.add('b3')
        chunk_has_grade = True
    if 'b4.' in chunk_lower or 'basic 4' in chunk_lower:
        chunk_grades.add('b4')
        chunk_has_grade = True
    if 'b5.' in chunk_lower or 'basic 5' in chunk_lower:
        chunk_grades.add('b5')
        chunk_has_grade = True
    if 'b6.' in chunk_lower or 'basic 6' in chunk_lower:
        chunk_grades.add('b6')
        chunk_has_grade = True
    
    # Check if grades match
    if query_has_grade and chunk_has_grade:
        if query_grades.intersection(chunk_grades):
            grades_match = True
        else:
            # SEVERE PENALTY: Query asks for specific grade but chunk is different grade
            grade_penalty = -0.7  # This will dramatically reduce the score
    elif query_has_grade and not chunk_has_grade:
        # Chunk doesn't specify grade but query does - moderate penalty
        grade_penalty = -0.3
    
    # Calculate token overlap score with weights
    intersection = query_tokens_filtered.intersection(chunk_tokens)
    
    # Weight important educational terms higher
    weighted_matches = 0.0
    for token in intersection:
        if token in important_terms:
            weighted_matches += 1.5  # Important terms get 1.5x weight
        else:
            weighted_matches += 1.0
    
    overlap_score = weighted_matches / len(query_tokens_filtered)
    
    # Bonus for exact phrase matches (2-3 word phrases)
    phrase_bonus = 0.0
    query_words = query_lower.split()
    
    # Check 2-word phrases
    for i in range(len(query_words) - 1):
        phrase = f"{query_words[i]} {query_words[i+1]}"
        if phrase in chunk_lower:
            phrase_bonus += 0.15
    
    # Check 3-word phrases (higher bonus)
    for i in range(len(query_words) - 2):
        phrase = f"{query_words[i]} {query_words[i+1]} {query_words[i+2]}"
        if phrase in chunk_lower:
            phrase_bonus += 0.25
    
    # Bonus for grade matching
    grade_bonus = 0.4 if grades_match else 0.0
    
    # Apply grade penalty (can make score negative!)
    total_score = overlap_score + phrase_bonus + grade_bonus + grade_penalty
    
    # Return score (can be negative to push mismatched grades to bottom)
    return max(0.0, total_score)  # Floor at 0 instead of allowing negative

async def fetch_context_chunks(db: AsyncSession, results: List[dict], window: int, subject: Optional[str], pillar: Optional[str]) -> List[dict]:
    """
    Fetch surrounding chunks for context to help with fragmented information.
    """
    enhanced_results = []
    seen_chunks = set()
    
    for result in results:
        knowledge_id = result["knowledge_id"]
        chunk_order = result["chunk_order"]
        
        # Get surrounding chunks
        where_conditions = ["ke.knowledge_id = :knowledge_id"]
        params = {
            "knowledge_id": knowledge_id,
            "start_order": max(0, chunk_order - window),
            "end_order": chunk_order + window
        }
        
        if subject:
            where_conditions.append("km.subject = :subject")
            params["subject"] = subject
        
        if pillar:
            where_conditions.append("km.pillar = :pillar")
            params["pillar"] = pillar
        
        where_clause = "WHERE " + " AND ".join(where_conditions)
        where_clause += " AND ke.chunk_order >= :start_order AND ke.chunk_order <= :end_order"
        
        sql_query = text(f"""
            SELECT 
                ke.chunk_text,
                ke.knowledge_id,
                ke.chunk_order,
                km.subject,
                km.pillar
            FROM knowledgeembedding ke
            JOIN knowledgemetadata km ON ke.knowledge_id = km.id
            {where_clause}
            ORDER BY ke.chunk_order
        """)
        
        context_result = await db.execute(sql_query, params)
        context_rows = context_result.fetchall()
        
        # Add all context chunks
        for row in context_rows:
            chunk_id = (row.knowledge_id, row.chunk_order)
            if chunk_id not in seen_chunks:
                seen_chunks.add(chunk_id)
                
                # Mark if this is the original matched chunk
                is_original = (row.chunk_order == chunk_order)
                
                enhanced_results.append({
                    "chunk_text": row.chunk_text,
                    "similarity": result["similarity"] if is_original else 0.0,
                    "knowledge_id": row.knowledge_id,
                    "subject": row.subject,
                    "pillar": row.pillar,
                    "chunk_order": row.chunk_order,
                    "keyword_score": result["keyword_score"] if is_original else 0.0,
                    "combined_score": result["combined_score"] if is_original else 0.0
                })
    
    return enhanced_results

def normalize_class_level(class_level: str) -> List[str]:
    """
    Normalize class level input and generate variations.
    Returns a list of variations to try in order of preference.
    
    Examples:
        "jhs 1" -> ["jhs1", "jhs 1", "jhs-1"]
        "class 2" -> ["class 2", "basic 2", "grade 2", "b2"]
        "basic 3" -> ["basic 3", "class 3", "grade 3", "b3"]
        "grade 5" -> ["grade 5", "basic 5", "class 5", "b5"]
    """
    if not class_level:
        return []
    
    class_lower = class_level.lower().strip()
    variations = [class_lower]  # Always include original
    
    # Extract the number
    import re
    number_match = re.search(r'\d+', class_lower)
    if not number_match:
        return variations
    
    number = number_match.group()
    
    # Generate variations based on input
    if 'jhs' in class_lower:
        # JHS variations
        variations.extend([
            f"jhs{number}",
            f"jhs {number}",
            f"jhs-{number}",
            f"junior high school {number}",
            f"junior high {number}"
        ])
    elif 'class' in class_lower:
        # Class -> Basic -> Grade -> B
        variations.extend([
            f"class {number}",
            f"basic {number}",
            f"grade {number}",
            f"b{number}"
        ])
    elif 'basic' in class_lower:
        # Basic -> Class -> Grade -> B
        variations.extend([
            f"basic {number}",
            f"class {number}",
            f"grade {number}",
            f"b{number}"
        ])
    elif 'grade' in class_lower:
        # Grade -> Basic -> Class -> B
        variations.extend([
            f"grade {number}",
            f"basic {number}",
            f"class {number}",
            f"b{number}"
        ])
    elif class_lower.startswith('b') and len(class_lower) <= 3:
        # B1, B2, etc -> expand to full names
        variations.extend([
            f"b{number}",
            f"basic {number}",
            f"class {number}",
            f"grade {number}"
        ])
    else:
        # Generic number - try all variations
        variations.extend([
            f"class {number}",
            f"basic {number}",
            f"grade {number}",
            f"b{number}",
            f"jhs{number}",
            f"jhs {number}"
        ])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for var in variations:
        if var not in seen:
            seen.add(var)
            unique_variations.append(var)
    
    return unique_variations

async def find_knowledge_by_class(db: AsyncSession, subject: str, pillar: str, class_variations: List[str]) -> Optional[int]:
    """
    Find knowledge document ID by searching notes field with class level variations.
    Returns the knowledge_id if found, None otherwise.
    """
    for variation in class_variations:
        # Search in notes field (case-insensitive)
        sql_query = text("""
            SELECT id, notes
            FROM knowledgemetadata
            WHERE subject = :subject 
            AND pillar = :pillar
            AND LOWER(notes) LIKE :class_pattern
            LIMIT 1
        """)
        
        result = await db.execute(
            sql_query, 
            {
                "subject": subject, 
                "pillar": pillar,
                "class_pattern": f"%{variation}%"
            }
        )
        row = result.fetchone()
        
        if row:
            logger.info(f"✅ Found curriculum document: ID={row.id}, Notes='{row.notes}', Matched variation='{variation}'")
            return row.id
    
    return None

def apply_grade_level_boost(results: List[dict], class_level: str, use_hybrid: bool) -> List[dict]:
    """
    Apply additional boosting to results that mention the specific grade level.
    This helps when a document contains multiple grade levels mixed together.
    """
    class_lower = class_level.lower()
    
    # Extract the number and type
    import re
    number_match = re.search(r'\d+', class_lower)
    if not number_match:
        return results
    
    number = number_match.group()
    
    # Generate patterns to look for in chunks
    grade_patterns = []
    if 'jhs' in class_lower:
        grade_patterns = [
            f"jhs{number}",
            f"jhs {number}",
            f"jhs-{number}",
            f"junior high school {number}",
            f"junior high {number}",
            f"year {number}"
        ]
    else:
        grade_patterns = [
            f"basic {number}",
            f"b{number}.",
            f"class {number}",
            f"grade {number}",
            f"year {number}"
        ]
    
    # Check each result and apply boost if it mentions the grade level
    for result in results:
        chunk_lower = result["chunk_text"].lower()
        mentions_target_grade = any(pattern in chunk_lower for pattern in grade_patterns)
        
        if mentions_target_grade:
            # Apply boost to score
            score_key = "combined_score" if use_hybrid else "similarity"
            result[score_key] = min(result[score_key] * 1.3, 1.0)  # 30% boost, capped at 1.0
            logger.debug(f"Boosted chunk mentioning {class_level}: new score = {result[score_key]}")
    
    # Re-sort after boosting
    sort_key = "combined_score" if use_hybrid else "similarity"
    results.sort(key=lambda x: x[sort_key], reverse=True)
    
    return results

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
        logger.info(f"Starting retrieval for query: '{request.query}' with filters - subject: {request.subject}, pillar: {request.pillar}, class: {request.class_level}")
        
        # If class_level is provided, find the specific document first
        knowledge_id_filter = None
        if request.class_level and request.subject and request.pillar:
            class_variations = normalize_class_level(request.class_level)
            logger.info(f"Searching for curriculum with class variations: {class_variations}")
            
            knowledge_id_filter = await find_knowledge_by_class(db, request.subject, request.pillar, class_variations)
            
            if not knowledge_id_filter:
                logger.warning(f"❌ No curriculum found for subject='{request.subject}', pillar='{request.pillar}', class='{request.class_level}'")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Curriculum not found for {request.subject} {request.pillar} at {request.class_level} level. Tried variations: {', '.join(class_variations[:5])}"
                )
            
            logger.info(f"✅ Will search only in document ID: {knowledge_id_filter}")
        
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
        
        # Build WHERE clause safely
        where_conditions = []
        params = {
            "query_embedding": query_embedding_array,
            # Fetch more results for better reranking with hybrid search
            "limit": request.limit * 5 if request.use_hybrid_search else request.limit
        }
        
        # Add knowledge_id filter if class level search was successful
        if knowledge_id_filter:
            where_conditions.append("km.id = :knowledge_id")
            params["knowledge_id"] = knowledge_id_filter
        
        if request.subject and not knowledge_id_filter:
            where_conditions.append("km.subject = :subject")
            params["subject"] = request.subject
            
        if request.pillar and not knowledge_id_filter:
            where_conditions.append("km.pillar = :pillar")
            params["pillar"] = request.pillar
            
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
        
        logger.info(f"Found {len(rows)} results from database")
        
        # Log unique knowledge_ids to help diagnose which documents are being retrieved
        unique_doc_ids = set(row.knowledge_id for row in rows)
        logger.info(f"Results from {len(unique_doc_ids)} unique documents with IDs: {sorted(unique_doc_ids)}")
        
        # For debugging: log sample chunk texts to see what grade levels are present
        if rows:
            sample_texts = [row.chunk_text[:100] for row in rows[:3]]
            logger.info(f"Sample chunk texts (first 100 chars): {sample_texts}")
        
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
                # Apply keyword boost multiplier
                boosted_keyword_score = keyword_score * request.keyword_boost
                
                # Adjust weights based on boosted keyword score strength
                if boosted_keyword_score > 0.5:
                    # Strong keyword match: 40% vector, 60% keyword
                    combined_score = (0.4 * similarity) + (0.6 * min(boosted_keyword_score, 1.0))
                else:
                    # Weak keyword match: 70% vector, 30% keyword
                    combined_score = (0.7 * similarity) + (0.3 * min(boosted_keyword_score, 1.0))
            
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
        
        # If class_level was specified, apply post-filtering to prioritize chunks mentioning that grade
        if request.class_level:
            all_results = apply_grade_level_boost(all_results, request.class_level, request.use_hybrid_search)
        
        # Apply limit after sorting (for hybrid search)
        if request.use_hybrid_search:
            all_results = all_results[:request.limit]
        
        # Optionally fetch context chunks (surrounding chunks)
        if request.context_window > 0 and all_results:
            all_results = await fetch_context_chunks(db, all_results, request.context_window, params.get("subject"), params.get("pillar"))
        
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
        
        if len(final_results) == 0:
            logger.warning(f"No results found above similarity threshold {request.min_similarity}")
        else:
            # Log top result score for debugging
            top_score = final_results[0].combined_score if request.use_hybrid_search else final_results[0].similarity
            logger.info(f"Top result score: {top_score}")
        
        return final_results
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"❌ Error during retrieval: {str(e)}", exc_info=True)
        
        # Provide more specific error messages
        error_detail = f"Retrieval failed: {str(e)}"
        if "dimension" in str(e).lower():
            error_detail = f"Embedding dimension mismatch - check model configuration. Error: {str(e)}"
        elif "connection" in str(e).lower() or "database" in str(e).lower():
            error_detail = f"Database connection failed. Error: {str(e)}"
        elif "embedding" in str(e).lower() and "dimension" not in str(e).lower():
            error_detail = f"Failed to process embeddings. Error: {str(e)}"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )