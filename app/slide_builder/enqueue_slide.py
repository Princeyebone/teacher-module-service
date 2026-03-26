"""
Enqueue slide generation tasks

Uses ARQ (async Redis queue) to queue slide generation for background processing.
This keeps the API responsive while slide generation happens asynchronously.
"""

import logging
from pathlib import Path
from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job
from typing import Optional
from datetime import datetime
from uuid import UUID

# Setup file logging
log_file = Path(__file__).parent / "slide_log.txt"
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [ENQUEUE] %(message)s')
file_handler.setFormatter(file_formatter)

# Create detailed logger
enqueue_logger = logging.getLogger("slide_enqueue")
enqueue_logger.setLevel(logging.INFO)
enqueue_logger.addHandler(file_handler)
enqueue_logger.propagate = False

logger = logging.getLogger(__name__)

# Redis settings - use database 7 for slides (separate from outline's database 6)
REDIS_SETTINGS = RedisSettings(host='localhost', port=6379, database=7)
QUEUE_NAME = 'slide_queue'


async def enqueue_slide_generation(
    teacher_id: str,
    subject: str,
    class_name: str,
    topic: Optional[str] = None,
    country: Optional[str] = "Ghana",
    education_system: Optional[str] = None,
    education_level: Optional[str] = None,
    delay: int = 0
) -> Job:
    """
    Enqueue a slide generation task for background processing.
    
    Args:
        teacher_id: Teacher UUID string
        subject: Subject name
        class_name: Class name
        topic: Lesson topic (optional, fetched from curriculum if not provided)
        country: Teacher's country
        education_system: Education system
        education_level: Education level
        delay: Delay in seconds before processing
        
    Returns:
        ARQ Job object with job_id for status tracking
    """
    try:
        enqueue_logger.info("=" * 80)
        enqueue_logger.info(f"ENQUEUEING SLIDE TASK - {datetime.now().isoformat()}")
        enqueue_logger.info("=" * 80)
        enqueue_logger.info(f"Teacher ID: {teacher_id}")
        enqueue_logger.info(f"Subject: {subject}")
        enqueue_logger.info(f"Class: {class_name}")
        enqueue_logger.info(f"Topic: {topic or 'Auto-detect from curriculum'}")
        enqueue_logger.info(f"Country: {country}")
        enqueue_logger.info(f"Delay: {delay} seconds")
        
        # Create Redis pool
        redis = await create_pool(REDIS_SETTINGS)
        
        enqueue_logger.info(f"✅ Redis connected: {REDIS_SETTINGS.host}:{REDIS_SETTINGS.port}/db{REDIS_SETTINGS.database}")
        
        # Enqueue task
        job = await redis.enqueue_job(
            'process_slide_task',
            teacher_id,
            subject,
            class_name,
            topic,
            country,
            education_system,
            education_level,
            _queue_name=QUEUE_NAME,
            _defer_by=delay
        )
        
        enqueue_logger.info(f"✅ Task enqueued - Job ID: {job.job_id}")
        logger.info(f"✅ Slide task enqueued: {subject}/{class_name} - Job {job.job_id}")
        
        await redis.close()
        
        return job
        
    except Exception as e:
        enqueue_logger.error(f"❌ Failed to enqueue slide task: {e}")
        logger.error(f"❌ Failed to enqueue slide task: {e}")
        raise


async def enqueue_session_slides(
    teacher_id: str,
    session_id: str,
    subject: str,
    class_name: str,
    indicator_ids: list,
    country: str = "Ghana",
    delay: int = 0
) -> Job:
    """
    Enqueue slide generation for a specific session (timetable-triggered).
    
    Args:
        teacher_id: Teacher UUID
        session_id: Session UUID
        subject: Subject name
        class_name: Class name
        indicator_ids: List of curriculum indicator IDs
        country: Country
        delay: Delay in seconds
        
    Returns:
        ARQ Job object
    """
    try:
        enqueue_logger.info("=" * 80)
        enqueue_logger.info(f"ENQUEUEING SESSION SLIDE TASK - {datetime.now().isoformat()}")
        enqueue_logger.info("=" * 80)
        enqueue_logger.info(f"Teacher: {teacher_id}")
        enqueue_logger.info(f"Session: {session_id}")
        enqueue_logger.info(f"Subject: {subject}")
        enqueue_logger.info(f"Class: {class_name}")
        enqueue_logger.info(f"Indicators: {indicator_ids}")
        
        redis = await create_pool(REDIS_SETTINGS)
        
        job = await redis.enqueue_job(
            'process_session_slide_task',
            teacher_id,
            session_id,
            subject,
            class_name,
            indicator_ids,
            country,
            _queue_name=QUEUE_NAME,
            _defer_by=delay
        )
        
        enqueue_logger.info(f"✅ Session slide task enqueued - Job ID: {job.job_id}")
        
        await redis.close()
        return job
        
    except Exception as e:
        enqueue_logger.error(f"❌ Failed to enqueue session slide task: {e}")
        raise


async def get_slide_job_status(job_id: str) -> dict:
    """
    Get the status of a slide generation job.
    
    Args:
        job_id: Job ID from enqueue
        
    Returns:
        Job status dict with status and result
    """
    try:
        redis = await create_pool(REDIS_SETTINGS)
        
        job = Job(job_id, redis)
        status = await job.status()
        
        result = {
            "job_id": job_id,
            "status": status.value if status else "unknown"
        }
        
        # Try to get result if job is complete
        if status and status.value == "complete":
            try:
                job_result = await job.result(timeout=1)
                result["result"] = job_result
            except:
                pass
        
        await redis.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}")
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(e)
        }
