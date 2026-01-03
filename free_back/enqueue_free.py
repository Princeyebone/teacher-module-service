"""
Enqueue function for Free Plan Tasks

Enqueue AI-powered semester plan generation without document uploads.
"""

import logging
from typing import Optional, Dict
from arq import create_pool
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)

# Redis settings for free plan queue
free_plan_redis_settings = RedisSettings(
    host="localhost",
    port=6379,
    database=5,  # Different database from curriculum (db 4) and semplan (db 3)
    conn_timeout=10,
    conn_retries=5,
    conn_retry_delay=1
)


async def enqueue_free_plan(
    teacher_id: str,
    subject: str,
    class_name: str,
    pupils: str,
    academic_level: str,
    education_system: str,
    session_data: Dict = None,
    topic_description: str = None,
    learning_objective: str = None,
    delay: int = 0
):
    """
    Enqueue a free plan generation task.
    
    Args:
        teacher_id: UUID string of the teacher
        subject: Subject/Course name
        class_name: Class name/section
        pupils: Pupil/Class level (e.g., "Level 100", "Grade 4")
        academic_level: Academic level (university/college/k12/other)
        education_system: Education system
        session_data: Session data with weekly sessions
        topic_description: Optional topic to focus on
        learning_objective: Optional learning objectives
        delay: Delay in seconds before processing
        
    Returns:
        Job object, or None if failed
    """
    try:
        logger.info(f"📤 Enqueueing free plan for teacher {teacher_id}")
        logger.info(f"   Subject: {subject}, Class: {class_name}, Pupils: {pupils}")
        logger.info(f"   Academic Level: {academic_level}, System: {education_system}")
        logger.info(f"   Topic: {topic_description if topic_description else 'None'}")
        logger.info(f"   Objective: {learning_objective if learning_objective else 'None'}")
        
        redis = await create_pool(free_plan_redis_settings)
        
        try:
            defer_by = None
            if delay > 0:
                from datetime import timedelta
                defer_by = timedelta(seconds=delay)
                logger.info(f"   Delay: {delay} seconds")
            
            job = await redis.enqueue_job(
                'process_free_plan_task',
                teacher_id,
                subject,
                class_name,
                pupils,
                academic_level,
                education_system,
                session_data,
                topic_description,
                learning_objective,
                _queue_name="free_plan_queue",
                _defer_by=defer_by
            )
            
            logger.info(f"✅ Free plan task enqueued - Job ID: {job.job_id}")
            return job
            
        finally:
            await redis.aclose()
            
    except Exception as e:
        logger.error(f"❌ Failed to enqueue free plan: {e}")
        return None
