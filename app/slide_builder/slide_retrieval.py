"""
Slide Retrieval Module

Retrieves relevant knowledge chunks from multiple pillars to enhance
AI-generated lesson slides.

Pillars retrieved:
- Cognitive Science & Pedagogy: 2 chunks (learning psychology)
- Subject Specific Knowledge: 3 chunks (most important)
- Lesson Design: 1 chunk (lesson structure)
- Evaluation: 1 chunk (assessment methods)

BATCH EMBEDDINGS: All queries are embedded in a single batch call.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

# Configure logging
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "slide_log.txt")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

retrieval_logger = logging.getLogger("slide_retrieval")
retrieval_logger.setLevel(logging.INFO)
retrieval_logger.addHandler(file_handler)
retrieval_logger.propagate = False


def build_pillar_queries(
    subject: str,
    class_name: str,
    topic: str,
    indicator_text: Optional[str] = None,
    content_standard: Optional[str] = None,
    strand_name: Optional[str] = None
) -> Dict[str, str]:
    """
    Build all queries for each pillar upfront.
    
    Returns:
        Dictionary with pillar names as keys and query strings as values
    """
    queries = {}
    
    # 1. COGNITIVE SCIENCE & PEDAGOGY
    queries["cognitive"] = f"""
    cognitive science learning principles
    student learning psychology
    effective teaching strategies for {class_name} students
    how students learn {subject}
    memory and retention in education
    engagement and motivation in classroom
    """.strip()
    
    # 2. SUBJECT SPECIFIC KNOWLEDGE - 3 chunks (MOST IMPORTANT)
    # Search specifically for this subject and topic
    # NOTE: User explicitly requested to use "subject specific knowledge" pillar and NOT syllabus
    queries["subject_knowledge"] = f"""
    {subject} {class_name}
    {topic}
    {indicator_text or ''}
    {content_standard or ''}
    {strand_name or ''}
    teaching {subject} concepts
    """.strip()
    
    # 3. LESSON DESIGN
    queries["lesson_design"] = f"""
    lesson design strategies
    how to structure a {subject} lesson
    lesson planning for {class_name}
    teaching activities and methods
    lesson introduction and engagement
    """.strip()
    
    # 4. EVALUATION
    queries["evaluation"] = f"""
    assessment methods for {subject}
    evaluation strategies {class_name}
    formative assessment techniques
    checking student understanding
    quiz and test design
    """.strip()
    
    return queries


async def generate_batch_embeddings(queries: Dict[str, str]) -> Dict[str, List[float]]:
    """
    Generate embeddings for all queries in a single batch call.
    
    Returns:
        Dictionary with pillar names as keys and embeddings as values
    """
    try:
        from app.rag.embedding import generate_embeddings_with_gemini
    except ImportError as e:
        logger.error(f"Failed to import embedding function: {e}")
        return {}
    
    # Prepare batch
    pillar_names = list(queries.keys())
    query_texts = list(queries.values())
    
    retrieval_logger.info(f"🔄 Generating batch embeddings for {len(query_texts)} queries")
    
    # Generate all embeddings in one batch call
    embeddings = generate_embeddings_with_gemini(query_texts)
    
    if not embeddings:
        retrieval_logger.error("Failed to generate batch embeddings")
        return {}
    
    # Map embeddings back to pillar names
    result = {}
    for i, pillar_name in enumerate(pillar_names):
        if embeddings[i]:
            result[pillar_name] = embeddings[i]
            retrieval_logger.info(f"✅ Embedding generated for {pillar_name}")
        else:
            retrieval_logger.warning(f"⚠️ No embedding for {pillar_name}")
    
    return result


async def search_pillar_with_embedding(
    pillar_pattern: str,
    query_embedding: List[float],
    teacher_id: Optional[UUID] = None,
    subject: Optional[str] = None,
    limit: int = 2,
    min_similarity: float = 0.15
) -> List[Dict[str, Any]]:
    """
    Search a pillar using a pre-computed embedding.
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    query_embedding_array = "[" + ",".join(str(x) for x in query_embedding) + "]"
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        results = []
        
        # Step 1: Try teacher-specific chunks first
        if teacher_id:
            if subject:
                teacher_query = text("""
                    SELECT 
                        ke.chunk_text,
                        ke.knowledge_id,
                        ke.chunk_order,
                        km.subject,
                        km.pillar,
                        km.notes,
                        km.teacher_id,
                        km.level,
                        ke.embedding <=> :query_embedding AS cosine_distance
                    FROM knowledgeembedding ke
                    JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                    WHERE LOWER(km.pillar) ILIKE :pillar_pattern
                      AND km.teacher_id = CAST(:teacher_id AS uuid)
                      AND LOWER(km.subject) ILIKE :subject_pattern
                    ORDER BY ke.embedding <=> :query_embedding
                    LIMIT :limit
                """)
                params = {
                    "query_embedding": query_embedding_array,
                    "pillar_pattern": f"%{pillar_pattern}%",
                    "teacher_id": str(teacher_id),
                    "subject_pattern": f"%{subject}%",
                    "limit": limit
                }
            else:
                teacher_query = text("""
                    SELECT 
                        ke.chunk_text,
                        ke.knowledge_id,
                        ke.chunk_order,
                        km.subject,
                        km.pillar,
                        km.notes,
                        km.teacher_id,
                        km.level,
                        ke.embedding <=> :query_embedding AS cosine_distance
                    FROM knowledgeembedding ke
                    JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                    WHERE LOWER(km.pillar) ILIKE :pillar_pattern
                      AND km.teacher_id = CAST(:teacher_id AS uuid)
                    ORDER BY ke.embedding <=> :query_embedding
                    LIMIT :limit
                """)
                params = {
                    "query_embedding": query_embedding_array,
                    "pillar_pattern": f"%{pillar_pattern}%",
                    "teacher_id": str(teacher_id),
                    "limit": limit
                }
            
            result = await db.execute(teacher_query, params)
            rows = result.fetchall()
            
            for row in rows:
                similarity = 1 - row.cosine_distance
                if similarity >= min_similarity:
                    results.append({
                        "chunk_text": row.chunk_text,
                        "similarity": round(similarity, 4),
                        "knowledge_id": row.knowledge_id,
                        "pillar": row.pillar,
                        "subject": row.subject,
                        "notes": row.notes,
                        "level": row.level,
                        "teacher_specific": True
                    })
        
        # Step 2: If not enough teacher-specific, get general chunks
        if len(results) < limit:
            remaining = limit - len(results)
            
            if subject:
                general_query = text("""
                    SELECT 
                        ke.chunk_text,
                        ke.knowledge_id,
                        ke.chunk_order,
                        km.subject,
                        km.pillar,
                        km.notes,
                        km.teacher_id,
                        km.level,
                        ke.embedding <=> :query_embedding AS cosine_distance
                    FROM knowledgeembedding ke
                    JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                    WHERE LOWER(km.pillar) ILIKE :pillar_pattern
                      AND LOWER(km.subject) ILIKE :subject_pattern
                    ORDER BY ke.embedding <=> :query_embedding
                    LIMIT :limit
                """)
                params = {
                    "query_embedding": query_embedding_array,
                    "pillar_pattern": f"%{pillar_pattern}%",
                    "subject_pattern": f"%{subject}%",
                    "limit": remaining
                }
            else:
                general_query = text("""
                    SELECT 
                        ke.chunk_text,
                        ke.knowledge_id,
                        ke.chunk_order,
                        km.subject,
                        km.pillar,
                        km.notes,
                        km.teacher_id,
                        km.level,
                        ke.embedding <=> :query_embedding AS cosine_distance
                    FROM knowledgeembedding ke
                    JOIN knowledgemetadata km ON ke.knowledge_id = km.id
                    WHERE LOWER(km.pillar) ILIKE :pillar_pattern
                    ORDER BY ke.embedding <=> :query_embedding
                    LIMIT :limit
                """)
                params = {
                    "query_embedding": query_embedding_array,
                    "pillar_pattern": f"%{pillar_pattern}%",
                    "limit": remaining
                }
            
            result = await db.execute(general_query, params)
            rows = result.fetchall()
            
            for row in rows:
                similarity = 1 - row.cosine_distance
                if similarity >= min_similarity:
                    # Avoid duplicates
                    if not any(r["knowledge_id"] == row.knowledge_id and 
                              r["chunk_text"][:100] == row.chunk_text[:100] for r in results):
                        results.append({
                            "chunk_text": row.chunk_text,
                            "similarity": round(similarity, 4),
                            "knowledge_id": row.knowledge_id,
                            "pillar": row.pillar,
                            "subject": row.subject,
                            "notes": row.notes,
                            "level": row.level,
                            "teacher_specific": False
                        })
        
        # Sort by similarity and take top results
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
        
    finally:
        await db_gen.aclose()


async def retrieve_all_pillars_for_slides(
    subject: str,
    class_name: str,
    topic: str,
    indicator_text: Optional[str] = None,
    content_standard: Optional[str] = None,
    strand_name: Optional[str] = None,
    teacher_id: Optional[UUID] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieve knowledge chunks from all 4 pillars for slide generation.
    
    Uses BATCH EMBEDDING - all queries are embedded in a single API call.
    
    Returns:
        Dictionary with pillar names as keys and chunk lists as values
    """
    retrieval_logger.info("\n" + "=" * 80)
    retrieval_logger.info("SLIDE RETRIEVAL - ALL PILLARS (BATCH MODE)")
    retrieval_logger.info("=" * 80)
    retrieval_logger.info(f"Subject: {subject}")
    retrieval_logger.info(f"Class: {class_name}")
    retrieval_logger.info(f"Topic: {topic}")
    retrieval_logger.info(f"Indicator: {indicator_text[:100] if indicator_text else 'N/A'}...")
    retrieval_logger.info(f"Teacher ID: {teacher_id}")
    
    # Step 1: Build all queries
    queries = build_pillar_queries(
        subject=subject,
        class_name=class_name,
        topic=topic,
        indicator_text=indicator_text,
        content_standard=content_standard,
        strand_name=strand_name
    )
    
    retrieval_logger.info(f"\n📝 Built {len(queries)} queries for batch embedding")
    for pillar, query in queries.items():
        retrieval_logger.info(f"  {pillar}: {query[:80]}...")
    
    # Step 2: Generate all embeddings in ONE batch call
    retrieval_logger.info("\n🔄 Generating embeddings in batch...")
    embeddings = await generate_batch_embeddings(queries)
    
    if not embeddings:
        retrieval_logger.error("❌ Failed to generate batch embeddings")
        return {"cognitive_science": [], "subject_knowledge": [], "lesson_design": [], "evaluation": []}
    
    retrieval_logger.info(f"✅ Generated {len(embeddings)} embeddings")
    
    # Step 3: Search each pillar using pre-computed embeddings
    all_chunks = {}
    
    # Cognitive Science - 2 chunks
    if "cognitive" in embeddings:
        retrieval_logger.info("\n--- Searching COGNITIVE pillar ---")
        cognitive_chunks = await search_pillar_with_embedding(
            pillar_pattern="cognitive",
            query_embedding=embeddings["cognitive"],
            teacher_id=teacher_id,
            limit=2,
            min_similarity=0.15
        )
        all_chunks["cognitive_science"] = cognitive_chunks
        log_chunks("cognitive_science", cognitive_chunks)
    else:
        all_chunks["cognitive_science"] = []
    
    # Subject Knowledge - 3 chunks
    if "subject_knowledge" in embeddings:
        retrieval_logger.info("\n--- Searching SUBJECT SPECIFIC KNOWLEDGE pillar ---")
        # Use 'subject specific knowledge' as confirmed in database
        subject_chunks = await search_pillar_with_embedding(
            pillar_pattern="subject specific knowledge",
            query_embedding=embeddings["subject_knowledge"],
            teacher_id=teacher_id,
            subject=subject,  # Filter by subject
            limit=3,
            min_similarity=0.15
        )
        
        # NOTE: Fallback to syllabus removed as per user instruction
        # to strictly use "subject specific knowledge" pillar.
        
        all_chunks["subject_knowledge"] = subject_chunks
        log_chunks("subject_knowledge", all_chunks["subject_knowledge"])
    else:
        all_chunks["subject_knowledge"] = []
    
    # Lesson Design - 1 chunk
    if "lesson_design" in embeddings:
        retrieval_logger.info("\n--- Searching LESSON DESIGN pillar ---")
        lesson_chunks = await search_pillar_with_embedding(
            pillar_pattern="lesson design",
            query_embedding=embeddings["lesson_design"],
            teacher_id=teacher_id,
            limit=1,
            min_similarity=0.15
        )
        all_chunks["lesson_design"] = lesson_chunks
        log_chunks("lesson_design", lesson_chunks)
    else:
        all_chunks["lesson_design"] = []
    
    # Evaluation - 1 chunk
    if "evaluation" in embeddings:
        retrieval_logger.info("\n--- Searching EVALUATION pillar ---")
        eval_chunks = await search_pillar_with_embedding(
            pillar_pattern="evaluation",
            query_embedding=embeddings["evaluation"],
            teacher_id=teacher_id,
            limit=1,
            min_similarity=0.15
        )
        
        # Fallback to assessment if empty
        if not eval_chunks:
            retrieval_logger.info("--- Trying ASSESSMENT pillar as fallback ---")
            eval_chunks = await search_pillar_with_embedding(
                pillar_pattern="assessment",
                query_embedding=embeddings["evaluation"],
                teacher_id=teacher_id,
                limit=1,
                min_similarity=0.15
            )
        
        all_chunks["evaluation"] = eval_chunks
        log_chunks("evaluation", eval_chunks)
    else:
        all_chunks["evaluation"] = []
    
    # Log summary
    retrieval_logger.info("\n" + "-" * 60)
    retrieval_logger.info("RETRIEVAL SUMMARY")
    retrieval_logger.info("-" * 60)
    for pillar, chunks in all_chunks.items():
        retrieval_logger.info(f"  {pillar}: {len(chunks)} chunks")
    retrieval_logger.info("=" * 80 + "\n")
    
    return all_chunks


def log_chunks(pillar_name: str, chunks: List[Dict[str, Any]]):
    """Log retrieved chunks for a pillar."""
    for i, chunk in enumerate(chunks):
        retrieval_logger.info(f"\nChunk {i+1}:")
        retrieval_logger.info(f"  Pillar: {chunk.get('pillar', 'N/A')}")
        retrieval_logger.info(f"  Subject: {chunk.get('subject', 'N/A')}")
        retrieval_logger.info(f"  Similarity: {chunk.get('similarity', 0)}")
        retrieval_logger.info(f"  Teacher-specific: {chunk.get('teacher_specific', False)}")
        retrieval_logger.info(f"  Notes: {str(chunk.get('notes', 'N/A'))[:100]}")
        retrieval_logger.info(f"  Text preview: {chunk['chunk_text'][:200]}...")


def format_chunks_for_ai_prompt(all_chunks: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Format all retrieved chunks into a structured section for the AI prompt.
    """
    if not any(all_chunks.values()):
        return ""
    
    formatted = "\n\n" + "=" * 60 + "\n"
    formatted += "KNOWLEDGE BASE REFERENCE MATERIAL\n"
    formatted += "=" * 60 + "\n\n"
    
    # Cognitive Science & Pedagogy
    if all_chunks.get("cognitive_science"):
        formatted += "### LEARNING PSYCHOLOGY & COGNITIVE SCIENCE ###\n"
        formatted += "(Use these insights to design cognitively effective slides)\n\n"
        for i, chunk in enumerate(all_chunks["cognitive_science"], 1):
            text = chunk["chunk_text"][:600] if len(chunk["chunk_text"]) > 600 else chunk["chunk_text"]
            formatted += f"[Reference {i}]\n{text}\n\n"
    
    # Subject Specific Knowledge
    if all_chunks.get("subject_knowledge"):
        formatted += "### SUBJECT-SPECIFIC CONTENT ###\n"
        formatted += "(This is your primary content source for the topic)\n\n"
        for i, chunk in enumerate(all_chunks["subject_knowledge"], 1):
            text = chunk["chunk_text"][:800] if len(chunk["chunk_text"]) > 800 else chunk["chunk_text"]
            formatted += f"[Reference {i}]\n{text}\n\n"
    
    # Lesson Design
    if all_chunks.get("lesson_design"):
        formatted += "### LESSON DESIGN PRINCIPLES ###\n"
        formatted += "(Apply these principles to structure your slides effectively)\n\n"
        for i, chunk in enumerate(all_chunks["lesson_design"], 1):
            text = chunk["chunk_text"][:500] if len(chunk["chunk_text"]) > 500 else chunk["chunk_text"]
            formatted += f"[Reference {i}]\n{text}\n\n"
    
    # Evaluation
    if all_chunks.get("evaluation"):
        formatted += "### ASSESSMENT & EVALUATION ###\n"
        formatted += "(Use these methods for your assessment slides)\n\n"
        for i, chunk in enumerate(all_chunks["evaluation"], 1):
            text = chunk["chunk_text"][:400] if len(chunk["chunk_text"]) > 400 else chunk["chunk_text"]
            formatted += f"[Reference {i}]\n{text}\n\n"
    
    formatted += "=" * 60 + "\n"
    
    return formatted
