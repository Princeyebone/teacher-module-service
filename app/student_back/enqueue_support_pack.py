"""
Enqueue student support pack generation tasks

Uses ARQ (async Redis queue) to queue pack generation for background processing.
"""

import logging
from pathlib import Path
from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job
from typing import Optional, List
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

# Redis settings - use database 8 for student support packs
REDIS_SETTINGS = RedisSettings(host='localhost', port=6379, database=8)
QUEUE_NAME = 'student_support_queue'


async def enqueue_student_support_pack(
    pack_id: str,
    teacher_id: str,
    student_name: str,
    subject: str,
    class_name: str,
    topic: str,
    interests: List[str],
    health_considerations: Optional[str],
    edu_sys: Optional[str] = None,
    edu_lvl: Optional[str] = None,
    delay: int = 0
) -> Job:
    """
    Enqueue a student support pack generation task.
    
    Args:
        pack_id: UUID of the pack in database
        teacher_id: Teacher UUID
        student_name: Student's name
        subject: Subject name
        class_name: Class name
        topic: Lesson topic
        interests: Student's interests
        health_considerations: Special needs/considerations
        edu_sys: Education system
        edu_lvl: Education level
        delay: Delay in seconds before processing
        
    Returns:
        ARQ Job object with job_id for status tracking
    """
    try:
        logger.info("=" * 80)
        logger.info(f"ENQUEUEING STUDENT SUPPORT PACK - {datetime.now().isoformat()}")
        logger.info("=" * 80)
        logger.info(f"Pack ID: {pack_id}")
        logger.info(f"Student: {student_name}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Topic: {topic}")
        logger.info(f"Interests: {interests}")
        
        # Create Redis pool
        redis = await create_pool(REDIS_SETTINGS)
        
        logger.info(f"✅ Redis connected: {REDIS_SETTINGS.host}:{REDIS_SETTINGS.port}/db{REDIS_SETTINGS.database}")
        
        # Enqueue task
        job = await redis.enqueue_job(
            'process_student_support_pack',
            pack_id,
            teacher_id,
            student_name,
            subject,
            class_name,
            topic,
            interests,
            health_considerations,
            edu_sys,
            edu_lvl,
            _queue_name=QUEUE_NAME,
            _defer_by=delay
        )
        
        logger.info(f"✅ Task enqueued - Job ID: {job.job_id}")
        
        await redis.close()
        
        return job
        
    except Exception as e:
        logger.error(f"❌ Failed to enqueue student support pack: {e}")
        raise


async def get_pack_job_status(job_id: str) -> dict:
    """
    Get the status of a pack generation job.
    
    Args:
        job_id: Job ID from enqueue
        
    Returns:
        Job status dict
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
