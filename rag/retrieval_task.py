"""
Background task for RAG retrieval processing.

This module provides background task processing for retrieval queries,
allowing async retrieval operations to be queued and processed by ARQ workers.
"""

import logging
import sys
import traceback
from typing import List, Optional, Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Import embedding function
try:
    from rag.embedding import generate_embedding_with_gemini
    EMBEDDING_AVAILABLE = True
    logger.info("✅ Gemini embedding model available for retrieval")
except ImportError as e:
    EMBEDDING_AVAILABLE = False
    logger.error(f"❌ Failed to import embedding functions: {e}")


async def perform_retrieval(
    db_session,
    query: str,
    subject: Optional[str] = None,
    pillar: Optional[str] = None,
    class_level: Optional[str] = None,
    limit: int = 5,
    min_similarity: float = 0.3,
    use_hybrid_search: bool = True,
    keyword_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Core retrieval logic extracted for reuse in background tasks.
    
    Args:
        db_session: Active database session
        query: Search query string
        subject: Optional subject filter
        pillar: Optional pillar filter (e.g., "curriculum")
        class_level: Optional class level filter
        limit: Maximum number of results
        min_similarity: Minimum similarity threshold
        use_hybrid_search: Whether to combine vector + keyword search
        keyword_weight: Weight for keyword matching (0-1)
    
    Returns:
        List of retrieval results as dictionaries
    """
    from sqlalchemy import text
    
    logger.info(f"🔍 Performing retrieval for query: '{query}'")
    logger.info(f"   Filters - subject: {subject}, pillar: {pillar}, class: {class_level}")
    
    # Step 1: Find relevant documents based on metadata filters
    knowledge_id_filters = await find_knowledge_documents(
        db_session, subject, pillar, class_level
    )
    
    if knowledge_id_filters is not None and len(knowledge_id_filters) == 0:
        logger.warning("No documents match the provided filters")
        return []
    
    # Step 2: Generate embedding for the query
    if not EMBEDDING_AVAILABLE:
        raise RuntimeError("Embedding model not available")
    
    query_embedding = generate_embedding_with_gemini(query)
    
    if not query_embedding:
        raise RuntimeError("Failed to generate query embedding")
    
    if len(query_embedding) != 1536:
        raise RuntimeError(f"Embedding dimension mismatch: expected 1536, got {len(query_embedding)}")
    
    logger.info(f"✅ Generated query embedding with {len(query_embedding)} dimensions")
    
    # Step 3: Build and execute vector search query
    query_embedding_array = "[" + ",".join(str(x) for x in query_embedding) + "]"
    
    where_conditions = []
    params = {
        "query_embedding": query_embedding_array,
        "limit": limit * 3 if use_hybrid_search else limit
    }
    
    # Add knowledge_id filter if documents were found
    if knowledge_id_filters:
        placeholders = ",".join([f":kid_{i}" for i in range(len(knowledge_id_filters))])
        where_conditions.append(f"km.id IN ({placeholders})")
        for i, kid in enumerate(knowledge_id_filters):
            params[f"kid_{i}"] = kid
    
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    
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
    
    result = await db_session.execute(sql_query, params)
    rows = result.fetchall()
    
    logger.info(f"📊 Found {len(rows)} results from database")
    
    # Step 4: Process and score results
    all_results = []
    for row in rows:
        cosine_distance = row.cosine_distance
        similarity = 1 - cosine_distance
        
        keyword_score = 0.0
        combined_score = similarity
        
        if use_hybrid_search:
            keyword_score = calculate_keyword_score(query, row.chunk_text)
            vector_weight = 1 - keyword_weight
            combined_score = (vector_weight * similarity) + (keyword_weight * keyword_score)
        
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
    
    # Step 5: Sort and filter
    sort_key = "combined_score" if use_hybrid_search else "similarity"
    all_results.sort(key=lambda x: x[sort_key], reverse=True)
    
    if use_hybrid_search:
        all_results = all_results[:limit]
    
    # Apply minimum similarity threshold
    final_results = [r for r in all_results if r["similarity"] >= min_similarity]
    
    logger.info(f"✅ Retrieved {len(final_results)} results above threshold ({min_similarity})")
    
    return final_results


def calculate_keyword_score(query: str, chunk_text: str) -> float:
    """
    Calculate simple keyword-based relevance score using token overlap.
    """
    query_lower = query.lower()
    chunk_lower = chunk_text.lower()
    
    query_tokens = set(query_lower.split())
    chunk_tokens = set(chunk_lower.split())
    
    if not query_tokens:
        return 0.0
    
    intersection = query_tokens.intersection(chunk_tokens)
    overlap_score = len(intersection) / len(query_tokens)
    
    phrase_bonus = 0.2 if query_lower in chunk_lower else 0.0
    
    return min(overlap_score + phrase_bonus, 1.0)


async def find_knowledge_documents(
    db_session,
    subject: Optional[str],
    pillar: Optional[str],
    class_level: Optional[str]
) -> Optional[List[int]]:
    """
    Find knowledge document IDs by filtering on metadata fields using ILIKE.
    """
    from sqlalchemy import text
    
    if not any([subject, pillar, class_level]):
        return None
    
    where_conditions = []
    params = {}
    
    if subject:
        where_conditions.append("subject ILIKE :subject")
        params["subject"] = f"%{subject}%"
    
    if pillar:
        where_conditions.append("pillar ILIKE :pillar")
        params["pillar"] = f"%{pillar}%"
    
    if class_level:
        where_conditions.append("(level ILIKE :class_level OR notes ILIKE :class_level)")
        params["class_level"] = f"%{class_level}%"
    
    where_clause = " AND ".join(where_conditions)
    
    sql_query = text(f"""
        SELECT id FROM knowledgemetadata
        WHERE {where_clause}
    """)
    
    result = await db_session.execute(sql_query, params)
    rows = result.fetchall()
    
    if rows:
        knowledge_ids = [row.id for row in rows]
        logger.info(f"✅ Found {len(knowledge_ids)} documents matching filters")
        return knowledge_ids
    else:
        logger.warning(f"❌ No documents found matching filters")
        return []


async def process_retrieval_task(
    ctx: dict,
    teacher_id: str,
    query: str,
    subject: Optional[str] = None,
    pillar: Optional[str] = None,
    class_level: Optional[str] = None,
    limit: int = 5,
    min_similarity: float = 0.3,
    use_hybrid_search: bool = True,
    keyword_weight: float = 0.3
):
    """
    ARQ background task for processing retrieval queries.
    
    Args:
        ctx: ARQ context
        teacher_id: UUID string of the teacher
        query: Search query string
        subject: Optional subject filter
        pillar: Optional pillar filter
        class_level: Optional class level filter
        limit: Maximum number of results
        min_similarity: Minimum similarity threshold
        use_hybrid_search: Whether to combine vector + keyword search
        keyword_weight: Weight for keyword matching
    
    Returns:
        Dictionary with retrieval results
    """
    logger.info(f"🚀 Starting retrieval task for teacher {teacher_id}")
    logger.info(f"🔍 Query: '{query}'")
    logger.info(f"📝 Filters - subject: {subject}, pillar: {pillar}, class: {class_level}")
    
    try:
        # Import database functions
        from database import get_db
        
        # Import WebSocket publishing function
        try:
            from sch_ground.background import publish_ws_message, save_notification
        except ImportError as e:
            logger.error(f"Failed to import WebSocket functions: {e}")
            raise
        
        # Send initial status update
        await publish_ws_message(teacher_id, {
            "status": "processing",
            "message": f"Searching for: {query}",
            "task_type": "retrieval"
        })
        
        # Get database session
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Perform retrieval
            results = await perform_retrieval(
                db,
                query=query,
                subject=subject,
                pillar=pillar,
                class_level=class_level,
                limit=limit,
                min_similarity=min_similarity,
                use_hybrid_search=use_hybrid_search,
                keyword_weight=keyword_weight
            )
            
            # Format results for response
            formatted_results = [
                {
                    "chunk_text": r["chunk_text"],
                    "similarity": round(r["similarity"], 4),
                    "knowledge_id": r["knowledge_id"],
                    "subject": r["subject"],
                    "pillar": r["pillar"],
                    "chunk_index": r["chunk_order"],
                    "keyword_match_score": round(r["keyword_score"], 4) if use_hybrid_search else None,
                    "combined_score": round(r["combined_score"], 4) if use_hybrid_search else None
                }
                for r in results
            ]
            
            logger.info(f"✅ Retrieval completed with {len(formatted_results)} results")
            
        finally:
            await db_gen.aclose()
        
        # Send success notification
        await publish_ws_message(teacher_id, {
            "status": "completed",
            "message": f"Found {len(formatted_results)} results for: {query}",
            "results": formatted_results,
            "task_type": "retrieval"
        })
        
        await save_notification(
            teacher_id=teacher_id,
            title="Search Completed",
            message=f"Found {len(formatted_results)} results for your query",
            type_="success"
        )
        
        return {
            "status": "success",
            "query": query,
            "results_count": len(formatted_results),
            "results": formatted_results
        }
        
    except Exception as e:
        error_msg = f"Retrieval failed for query '{query}': {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        # Send error notification
        await publish_ws_message(teacher_id, {
            "status": "error",
            "message": f"Search failed: {str(e)}",
            "error": str(e),
            "task_type": "retrieval"
        })
        
        await save_notification(
            teacher_id=teacher_id,
            title="Search Failed",
            message=f"Failed to search for '{query}': {str(e)}",
            type_="error"
        )
        
        raise RuntimeError(error_msg)
