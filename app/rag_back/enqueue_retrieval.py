"""
Enqueue function for Retrieval Tasks

This module provides a convenient function to enqueue retrieval tasks
to the ARQ worker queue.

Usage:
    from app.rag_back.enqueue_retrieval import enqueue_retrieval_task
    
    job = await enqueue_retrieval_task(
        teacher_id="uuid-string",
        query="What are the learning objectives?",
        subject="Mathematics",
        pillar="curriculum",
        class_level="Basic 4"
    )
"""

import logging
from typing import Optional
from arq import create_pool
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)

# Redis settings - must match retrieval_worker.py
retrieval_redis_settings = RedisSettings(
    host="localhost", 
    port=6379, 
    database=3,  # Same as retrieval_worker.py
    conn_timeout=10, 
    conn_retries=5, 
    conn_retry_delay=1
)


async def enqueue_retrieval_task(
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
    Enqueue a retrieval task to the ARQ worker queue.
    
    Args:
        teacher_id: UUID string of the teacher (required for notifications)
        query: Search query string (required)
        subject: Optional subject filter (e.g., "Mathematics")
        pillar: Optional pillar filter (e.g., "curriculum", "syllabus")
        class_level: Optional class level filter (e.g., "Basic 4", "JHS 1")
        limit: Maximum number of results (default: 5)
        min_similarity: Minimum similarity threshold (default: 0.3)
        use_hybrid_search: Combine vector + keyword search (default: True)
        keyword_weight: Weight for keyword matching 0-1 (default: 0.3)
    
    Returns:
        Job object with job_id, or None if enqueueing failed
    
    Example:
        job = await enqueue_retrieval_task(
            teacher_id="7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
            query="What are fractions?",
            subject="Mathematics",
            pillar="curriculum",
            class_level="Basic 4"
        )
        print(f"Job ID: {job.job_id}")
    """
    try:
        logger.info(f"📤 Enqueueing retrieval task for teacher {teacher_id}")
        logger.info(f"   Query: '{query}'")
        logger.info(f"   Filters: subject={subject}, pillar={pillar}, class={class_level}")
        
        # Create Redis connection pool
        redis = await create_pool(retrieval_redis_settings)
        
        try:
            # Enqueue the task
            job = await redis.enqueue_job(
                'process_retrieval_task',
                teacher_id,
                query,
                subject,
                pillar,
                class_level,
                limit,
                min_similarity,
                use_hybrid_search,
                keyword_weight,
                _queue_name="retrieval_queue"
            )
            
            logger.info(f"✅ Retrieval task enqueued successfully")
            logger.info(f"   Job ID: {job.job_id}")
            
            return job
            
        finally:
            await redis.aclose()
            
    except Exception as e:
        logger.error(f"❌ Failed to enqueue retrieval task: {e}")
        return None
