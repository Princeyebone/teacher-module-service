"""
Enqueue outline generation tasks
"""

import logging
import os
from pathlib import Path
from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Setup file logging
log_file = Path(__file__).parent / "log.txt"
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [ENQUEUE] %(message)s')
file_handler.setFormatter(file_formatter)

# Create detailed logger
enqueue_logger = logging.getLogger("outline_enqueue")
enqueue_logger.setLevel(logging.INFO)
enqueue_logger.addHandler(file_handler)
enqueue_logger.propagate = False

def log_separator():
    """Log separator for readability"""
    enqueue_logger.info("=" * 100)

def log_section(title: str):
    """Log section header"""
    enqueue_logger.info("")
    enqueue_logger.info("=" * 100)
    enqueue_logger.info(f"  {title}")
    enqueue_logger.info("=" * 100)

# Redis settings (must match worker)
REDIS_SETTINGS = RedisSettings(host='localhost', port=6379, database=6)
QUEUE_NAME = 'outline_queue'


async def enqueue_outline_generation(
    teacher_id: str,
    subject: str,
    class_name: str,
    education_system: Optional[str] = None,
    academic_level: Optional[str] = None,
    semester_name: Optional[str] = None,
    term: Optional[str] = None,
    delay: int = 0
) -> Job:
    """
    Enqueue an outline generation task.
    
    Args:
        teacher_id: Teacher UUID string
        subject: Subject name
        class_name: Class name
        education_system: Education system
        academic_level: Academic level
        semester_name: Semester name
        term: Term name
        delay: Delay in seconds before processing
        
    Returns:
        ARQ Job object
    """
    try:
        log_section(f"ENQUEUEING OUTLINE TASK - {datetime.now().isoformat()}")
        
        enqueue_logger.info(f"Teacher ID: {teacher_id}")
        enqueue_logger.info(f"Subject: {subject}")
        enqueue_logger.info(f"Class: {class_name}")
        enqueue_logger.info(f"Education System: {education_system or 'Not specified'}")
        enqueue_logger.info(f"Academic Level: {academic_level or 'Not specified'}")
        enqueue_logger.info(f"Semester: {semester_name or 'Not specified'}")
        enqueue_logger.info(f"Term: {term or 'Not specified'}")
        enqueue_logger.info(f"Delay: {delay} seconds")
        
        logger.info(f"Enqueueing outline generation for {subject} - {class_name}")
        
        enqueue_logger.info("")
        enqueue_logger.info("Connecting to Redis...")
        enqueue_logger.info(f"  Host: {REDIS_SETTINGS.host}")
        enqueue_logger.info(f"  Port: {REDIS_SETTINGS.port}")
        enqueue_logger.info(f"  Database: {REDIS_SETTINGS.database}")
        enqueue_logger.info(f"  Queue: {QUEUE_NAME}")
        
        # Create Redis pool
        redis = await create_pool(REDIS_SETTINGS)
        
        enqueue_logger.info("✅ Redis connection established")
        enqueue_logger.info("")
        enqueue_logger.info("Enqueueing task...")
        
        # Enqueue task
        job = await redis.enqueue_job(
            'process_outline_task',
            teacher_id,
            subject,
            class_name,
            education_system,
            academic_level,
            semester_name,
            term,
            _queue_name=QUEUE_NAME,
            _defer_by=delay
        )
        
        enqueue_logger.info("✅ Task enqueued successfully")
        enqueue_logger.info(f"  Job ID: {job.job_id}")
        enqueue_logger.info(f"  Queue: {QUEUE_NAME}")
        enqueue_logger.info(f"  Status: Queued")
        if delay > 0:
            enqueue_logger.info(f"  Will start in: {delay} seconds")
        
        log_separator()
        
        logger.info(f"✅ Outline task enqueued: Job ID {job.job_id}")
        
        await redis.close()
        
        return job
        
    except Exception as e:
        enqueue_logger.error(f"❌ Failed to enqueue outline task")
        enqueue_logger.error(f"   Error: {e}")
        enqueue_logger.error(f"   Exception type: {type(e).__name__}")
        log_separator()
        
        logger.error(f"❌ Failed to enqueue outline task: {e}")
        raise


async def get_outline_job_status(job_id: str) -> dict:
    """
    Get the status of an outline generation job.
    
    Args:
        job_id: Job ID from enqueue
        
    Returns:
        Job status dict
    """
    try:
        redis = await create_pool(REDIS_SETTINGS)
        
        job = Job(job_id, redis)
        status = await job.status()
        result = await job.result()
        
        await redis.close()
        
        return {
            "job_id": job_id,
            "status": status.value if status else "unknown",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(e)
        }
