"""
Enqueue Functions for Text Chunking Tasks

This module provides functions to enqueue text extraction and chunking tasks
for processing by the ARQ workers.

Usage:
    from rag_back.enqueue_text_chunking import enqueue_text_chunking_task
    
    job_id = await enqueue_text_chunking_task(
        teacher_id="teacher-uuid",
        file_path="/path/to/document.pdf",
        gcs_file_name="document.pdf",
        metadata={
            "subject": "Mathematics",
            "notes": "Algebra basics",
            "level": "Grade 8",
            "region": "Ghana",
            "source_url": "https://example.com/document.pdf",
            "file_path": "/gcs/path/document.pdf",
            "pillar": "curriculum"
        }
    )
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from arq import create_pool
from uuid import UUID

# Import worker configurations
try:
    from .text_chunking_worker import text_chunking_redis_settings
except ImportError:
    # If running as script directly, add parent directory to path
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    from rag_back.text_chunking_worker import text_chunking_redis_settings

logger = logging.getLogger(__name__)

async def enqueue_text_chunking_task(
    teacher_id: str,
    file_path: str,
    gcs_file_name: str,
    knowledge_id: int,
    metadata: Dict[str, Any],
    queue_name: str = "text_chunking_queue_1"
) -> Optional[str]:
    """
    Enqueue a text extraction and chunking task for background processing.
    
    Args:
        teacher_id: UUID string of the teacher (can be None for system/developer records)
        file_path: Path to the uploaded file
        gcs_file_name: File name in GCS
        knowledge_id: ID of the KnowledgeMetadata record
        metadata: Dictionary containing subject, notes, level, region, source_url, pillar, etc.
        queue_name: Name of the queue to enqueue the task to (default: text_chunking_queue_1)
        
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
    
    # Validate file_path exists
    import os
    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        return None
    
    try:
        # Create Redis connection pool
        redis = await create_pool(text_chunking_redis_settings)
        
        # Enqueue the task with the correct parameter order
        job = await redis.enqueue_job(
            'process_text_chunking_task',
            teacher_id,
            file_path,
            gcs_file_name,
            knowledge_id,
            metadata,
            _queue_name=queue_name
        )
        
        logger.info(f"✅ Text chunking task enqueued successfully")
        logger.info(f"   - Job ID: {job.job_id}")
        logger.info(f"   - Queue: {queue_name}")
        logger.info(f"   - File: {os.path.basename(file_path)}")
        logger.info(f"   - Knowledge ID: {knowledge_id}")
        
        await redis.aclose()
        return job.job_id
        
    except Exception as e:
        logger.error(f"❌ Failed to enqueue text chunking task: {e}")
        return None

async def enqueue_text_chunking_task_round_robin(
    teacher_id: str,
    file_path: str,
    gcs_file_name: str,
    knowledge_id: int,
    metadata: Dict[str, Any]
) -> Optional[str]:
    """
    Enqueue a text extraction and chunking task using round-robin distribution
    between the two queues for load balancing.
    
    Args:
        teacher_id: UUID string of the teacher
        file_path: Path to the uploaded file
        gcs_file_name: File name in GCS
        knowledge_id: ID of the KnowledgeMetadata record
        metadata: Dictionary containing subject, notes, level, region, source_url, pillar, etc.
        
    Returns:
        Job ID if successful, None if failed
    """
    # Simple round-robin: alternate between queues
    # In a production environment, you might want to check queue lengths
    import time
    queue_selector = int(time.time()) % 2
    queue_name = "text_chunking_queue_1" if queue_selector == 0 else "text_chunking_queue_2"
    
    return await enqueue_text_chunking_task(
        teacher_id=teacher_id,
        file_path=file_path,
        gcs_file_name=gcs_file_name,
        knowledge_id=knowledge_id,
        metadata=metadata,
        queue_name=queue_name
    )

# Convenience functions for direct use
def enqueue_text_chunking_sync(
    teacher_id: str,
    file_path: str,
    gcs_file_name: str,
    knowledge_id: int,
    metadata: Dict[str, Any],
    queue_name: str = "text_chunking_queue_1"
) -> Optional[str]:
    """
    Synchronous version of enqueue_text_chunking_task.
    
    Args:
        teacher_id: UUID string of the teacher (can be None for system/developer records)
        file_path: Path to the uploaded file
        gcs_file_name: File name in GCS
        knowledge_id: ID of the KnowledgeMetadata record
        metadata: Dictionary containing subject, notes, level, region, source_url, pillar, etc.
        queue_name: Name of the queue to enqueue the task to (default: text_chunking_queue_1)
        
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
    
    try:
        return asyncio.run(enqueue_text_chunking_task(
            teacher_id=teacher_id,
            file_path=file_path,
            gcs_file_name=gcs_file_name,
            knowledge_id=knowledge_id,
            metadata=metadata,
            queue_name=queue_name
        ))
    except Exception as e:
        logger.error(f"❌ Failed to enqueue text chunking task (sync): {e}")
        return None

def enqueue_text_chunking_round_robin_sync(
    teacher_id: str,
    file_path: str,
    gcs_file_name: str,
    knowledge_id: int,
    metadata: Dict[str, Any]
) -> Optional[str]:
    """
    Synchronous version of enqueue_text_chunking_task_round_robin.
    
    Args:
        teacher_id: UUID string of the teacher (can be None for system/developer records)
        file_path: Path to the uploaded file
        gcs_file_name: File name in GCS
        knowledge_id: ID of the KnowledgeMetadata record
        metadata: Dictionary containing subject, notes, level, region, source_url, pillar, etc.
        
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
    
    try:
        return asyncio.run(enqueue_text_chunking_task_round_robin(
            teacher_id=teacher_id,
            file_path=file_path,
            gcs_file_name=gcs_file_name,
            knowledge_id=knowledge_id,
            metadata=metadata
        ))
    except Exception as e:
        logger.error(f"❌ Failed to enqueue text chunking task (round-robin sync): {e}")
        return None

if __name__ == "__main__":
    # Example usage
    print("This module provides functions to enqueue text chunking tasks.")
    print("Import and use the functions in your application code.")