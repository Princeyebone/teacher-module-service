"""
Enqueue Functions for Embedding Generation Tasks

This module provides functions to enqueue embedding generation tasks
for processing by the ARQ worker.

Usage:
    from rag_back.enqueue_embedding import enqueue_embedding_task
    
    job_id = await enqueue_embedding_task(
        teacher_id="teacher-uuid",
        knowledge_id=123,
        chunks=["chunk1", "chunk2", "chunk3"],
        metadata={
            "subject": "Mathematics",
            "notes": "Algebra basics"
        }
    )
"""

import asyncio
import logging
import traceback
from typing import Dict, Any, Optional, List
from arq import create_pool
from uuid import UUID

# Import worker configurations
try:
    from .embedding_worker import embedding_redis_settings
except ImportError:
    # If running as script directly, add parent directory to path
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    from rag_back.embedding_worker import embedding_redis_settings

logger = logging.getLogger(__name__)

async def enqueue_embedding_task(
    teacher_id: str,
    knowledge_id: int,
    chunks: List[str],
    metadata: Dict[str, Any]
) -> Optional[str]:
    """
    Enqueue an embedding generation task for background processing.
    
    Args:
        teacher_id: UUID string of the teacher (can be None for system/developer records)
        knowledge_id: ID of the KnowledgeMetadata record
        chunks: List of text chunks to generate embeddings for
        metadata: Dictionary containing subject, notes, etc.
        
    Returns:
        Job ID if successful, None if failed
    """
    # Validate teacher_id is a valid UUID string (unless it's None for system/developer records)
    if teacher_id is not None:
        try:
            UUID(teacher_id)
        except ValueError:
            logger.error(f"Invalid teacher_id: {teacher_id}")
            return None
    elif teacher_id is None:
        logger.info("Processing embedding task for system/developer record (NULL teacher_id)")
    
    # Validate chunks
    if not chunks or not isinstance(chunks, list):
        logger.error(f"Invalid chunks: {chunks}")
        return None
    
    try:
        logger.info(f"Creating Redis connection pool for embedding task")
        # Create Redis connection pool
        redis = await create_pool(embedding_redis_settings)
        
        logger.info(f"Enqueuing embedding task for knowledge_id: {knowledge_id}")
        # Enqueue the task
        job = await redis.enqueue_job(
            'process_embedding_task',
            teacher_id,
            knowledge_id,
            chunks,
            metadata,
            _queue_name="embedding_queue"
        )
        
        logger.info(f"✅ Embedding task enqueued successfully")
        logger.info(f"   - Job ID: {job.job_id}")
        logger.info(f"   - Queue: embedding_queue")
        logger.info(f"   - Knowledge ID: {knowledge_id}")
        logger.info(f"   - Chunks: {len(chunks)}")
        
        await redis.aclose()
        return job.job_id
        
    except Exception as e:
        logger.error(f"❌ Failed to enqueue embedding task: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

# Convenience functions for direct use
def enqueue_embedding_sync(
    teacher_id: str,
    knowledge_id: int,
    chunks: List[str],
    metadata: Dict[str, Any]
) -> Optional[str]:
    """
    Synchronous version of enqueue_embedding_task.
    
    Args:
        teacher_id: UUID string of the teacher (can be None for system/developer records)
        knowledge_id: ID of the KnowledgeMetadata record
        chunks: List of text chunks to generate embeddings for
        metadata: Dictionary containing subject, notes, etc.
        
    Returns:
        Job ID if successful, None if failed
    """
    try:
        logger.info(f"Attempting to enqueue embedding task for knowledge_id: {knowledge_id}")
        logger.info(f"Teacher ID: {teacher_id}")
        logger.info(f"Number of chunks: {len(chunks)}")
        logger.info(f"Metadata: {metadata}")
        
        result = asyncio.run(enqueue_embedding_task(
            teacher_id=teacher_id,
            knowledge_id=knowledge_id,
            chunks=chunks,
            metadata=metadata
        ))
        
        logger.info(f"Embedding task enqueue result: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Failed to enqueue embedding task (sync): {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    # Example usage
    print("This module provides functions to enqueue embedding generation tasks.")
    print("Import and use the functions in your application code.")