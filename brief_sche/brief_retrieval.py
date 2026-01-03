"""
Lesson Brief Retrieval Module

Retrieves relevant lesson design chunks from the knowledge base
to enhance the AI-generated lesson briefs.
"""

import os
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Create file logger for detailed retrieval logs
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brief_log.txt")
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

retrieval_logger = logging.getLogger("brief_retrieval_detail")
retrieval_logger.setLevel(logging.INFO)
retrieval_logger.addHandler(file_handler)
retrieval_logger.propagate = False


async def retrieve_lesson_design_chunks(
    subject: str,
    class_name: str,
    strand: str,
    substrand: str,
    content_standard: str,
    indicators: List[Dict[str, str]],
    limit: int = 2,
    min_similarity: float = 0.25
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant lesson design chunks from the knowledge base.
    
    Args:
        subject: Subject name (e.g., "Mathematics", "Science")
        class_name: Class/grade level (e.g., "Basic 6", "JHS 1")
        strand: Curriculum strand
        substrand: Curriculum substrand
        content_standard: Content standard text
        indicators: List of indicator dictionaries with 'code' and 'text'
        limit: Maximum number of chunks to return (default 2)
        min_similarity: Minimum similarity threshold
        
    Returns:
        List of dictionaries containing chunk_text and similarity score
    """
    from database import get_db
    from sqlalchemy import text
    
    try:
        # Import embedding function
        from rag.embedding import generate_embedding_with_gemini
    except ImportError as e:
        logger.error(f"Failed to import embedding function: {e}")
        return []
    
    # Build a query focused on LESSON DESIGN methodology
    # The Lesson Design pillar contains general pedagogical content, NOT subject-specific curriculum
    # So we query for teaching strategies and lesson structure concepts
    
    # Create a pedagogical query that will match lesson design content
    query = """
    effective lesson design strategies
    how to structure a lesson
    student engagement techniques
    lesson introduction and hook
    teaching methods and activities
    formative assessment during lessons
    lesson pacing and transitions
    active learning strategies
    classroom interaction techniques
    """.strip()
    
    # Log the query to file
    retrieval_logger.info("=" * 60)
    retrieval_logger.info("RAG RETRIEVAL - LESSON DESIGN QUERY")
    retrieval_logger.info("=" * 60)
    retrieval_logger.info(f"Context - Subject: {subject}")
    retrieval_logger.info(f"Context - Class: {class_name}")
    retrieval_logger.info(f"Context - Strand: {strand}")
    retrieval_logger.info(f"Context - Substrand: {substrand}")
    retrieval_logger.info("-" * 40)
    retrieval_logger.info(f"QUERY (for Lesson Design pillar):\n{query}")
    retrieval_logger.info("=" * 60)
    
    logger.info(f"Retrieval query (lesson design focus): {query[:100]}...")
    
    try:
        # Generate embedding for the query
        query_embedding = generate_embedding_with_gemini(query)
        
        if not query_embedding:
            logger.warning("Failed to generate query embedding")
            retrieval_logger.warning("Failed to generate query embedding")
            return []
        
        logger.info(f"Generated query embedding with {len(query_embedding)} dimensions")
        retrieval_logger.info(f"Generated query embedding with {len(query_embedding)} dimensions")
        
        # Convert embedding to PostgreSQL array format
        query_embedding_array = "[" + ",".join(str(x) for x in query_embedding) + "]"
        
        # Get database connection
        db_gen = get_db()
        db = await anext(db_gen)
        
        try:
            # First, check how many records exist in lesson design pillar
            count_query = text("""
                SELECT COUNT(*) as cnt
                FROM knowledgeembedding ke
                JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                WHERE LOWER(km.pillar) = 'lesson design'
            """)
            count_result = await db.execute(count_query)
            count_row = count_result.fetchone()
            retrieval_logger.info(f"TOTAL CHUNKS IN 'lesson design': {count_row.cnt if count_row else 0}")
            
            # Search for relevant chunks using vector similarity
            # Search in lesson design pillar (LOWERCASE - that's where the embeddings are!)
            sql_query = text("""
                SELECT 
                    ke.chunk_text,
                    ke.knowledge_id,
                    ke.chunk_order,
                    km.subject,
                    km.pillar,
                    km.notes,
                    ke.embedding <=> :query_embedding AS cosine_distance
                FROM knowledgeembedding ke
                JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                WHERE LOWER(km.pillar) = 'lesson design'
                ORDER BY ke.embedding <=> :query_embedding
                LIMIT :limit
            """)
            
            retrieval_logger.info(f"Executing query with limit={limit * 3}")
            
            result = await db.execute(
                sql_query,
                {
                    "query_embedding": query_embedding_array,
                    "limit": limit * 3  # Fetch more for filtering
                }
            )
            rows = result.fetchall()
            
            logger.info(f"Found {len(rows)} potential chunks from database")
            retrieval_logger.info(f"Found {len(rows)} potential chunks from database")
            
            # Process and filter results
            chunks = []
            for row in rows:
                cosine_distance = row.cosine_distance
                similarity = 1 - cosine_distance
                
                # Apply minimum similarity threshold
                if similarity >= min_similarity:
                    chunks.append({
                        "chunk_text": row.chunk_text,
                        "similarity": round(similarity, 4),
                        "knowledge_id": row.knowledge_id,
                        "pillar": row.pillar,
                        "notes": row.notes
                    })
            
            # Sort by similarity and take top 'limit' chunks
            chunks.sort(key=lambda x: x["similarity"], reverse=True)
            final_chunks = chunks[:limit]
            
            logger.info(f"Returning {len(final_chunks)} chunks above threshold {min_similarity}")
            
            # Log retrieved chunks in detail
            retrieval_logger.info("-" * 60)
            retrieval_logger.info("RETRIEVED CHUNKS")
            retrieval_logger.info("-" * 60)
            
            for i, chunk in enumerate(final_chunks):
                logger.info(f"  Chunk {i+1}: similarity={chunk['similarity']}, pillar={chunk['pillar']}, notes={chunk.get('notes', 'N/A')[:50]}")
                
                # Log full chunk to file
                retrieval_logger.info(f"\n--- CHUNK {i+1} ---")
                retrieval_logger.info(f"Similarity: {chunk['similarity']}")
                retrieval_logger.info(f"Pillar: {chunk['pillar']}")
                retrieval_logger.info(f"Notes: {chunk.get('notes', 'N/A')}")
                retrieval_logger.info(f"Knowledge ID: {chunk['knowledge_id']}")
                retrieval_logger.info(f"Text:\n{chunk['chunk_text'][:1000]}...")
                retrieval_logger.info("-" * 40)
            
            if not final_chunks:
                retrieval_logger.info("No chunks met the similarity threshold")
            
            retrieval_logger.info("=" * 60)
            
            return final_chunks
            
        finally:
            await db_gen.aclose()
            
    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        retrieval_logger.error(f"Error during retrieval: {e}")
        return []


async def retrieve_chunks_for_lesson(
    subject: str,
    class_name: str,
    todays_lesson: Dict[str, Any],
    limit: int = 2
) -> List[Dict[str, Any]]:
    """
    Convenience function to retrieve chunks based on today's lesson context.
    
    Args:
        subject: Subject name
        class_name: Class/grade level
        todays_lesson: Dictionary with strand, substrand, content_standard, indicators
        limit: Maximum chunks to return
        
    Returns:
        List of retrieved chunks with text and similarity
    """
    if not todays_lesson:
        logger.warning("No lesson context provided for retrieval")
        return []
    
    return await retrieve_lesson_design_chunks(
        subject=subject,
        class_name=class_name,
        strand=todays_lesson.get("strand", ""),
        substrand=todays_lesson.get("substrand", ""),
        content_standard=todays_lesson.get("content_standard", ""),
        indicators=todays_lesson.get("indicators", []),
        limit=limit
    )


def format_retrieved_chunks_for_prompt(chunks: List[Dict[str, Any]]) -> str:
    """
    Format retrieved chunks for inclusion in the AI prompt.
    
    Args:
        chunks: List of retrieved chunk dictionaries
        
    Returns:
        Formatted string for the prompt
    """
    if not chunks:
        return ""
    
    formatted = "**LESSON DESIGN REFERENCE MATERIAL:**\n"
    formatted += "(The following excerpts are from pedagogical resources that may help with lesson delivery)\n\n"
    
    for i, chunk in enumerate(chunks, 1):
        formatted += f"--- Reference {i} ---\n"
        # Truncate long chunks to avoid overwhelming the prompt
        text = chunk.get("chunk_text", "")
        if len(text) > 800:
            text = text[:800] + "..."
        formatted += f"{text}\n\n"
    
    return formatted


# Test function
async def test_retrieval():
    """Test the retrieval function."""
    test_lesson = {
        "strand": "Algebra",
        "substrand": "Linear Equations",
        "content_standard": "Solve linear equations in one variable",
        "indicators": [
            {"code": "B6.1.2.1", "text": "Solve simple linear equations using addition and subtraction"}
        ]
    }
    
    chunks = await retrieve_chunks_for_lesson(
        subject="Mathematics",
        class_name="Basic 6",
        todays_lesson=test_lesson,
        limit=2
    )
    
    print(f"Retrieved {len(chunks)} chunks:")
    for chunk in chunks:
        print(f"  - Similarity: {chunk['similarity']}")
        print(f"    Text preview: {chunk['chunk_text'][:100]}...")
        print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_retrieval())
