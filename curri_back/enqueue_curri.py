"""
Enqueue function for Curriculum Processing Tasks

This module provides a convenient function to enqueue curriculum processing tasks
to the ARQ worker queue.

Usage:
    from curri_back.enqueue_curri import enqueue_curriculum_processing
    
    job = await enqueue_curriculum_processing(
        teacher_id="uuid-string",
        gcs_file_name="curriculum/teacher_id/class/subject.pdf",
        subject="Mathematics",
        class_name="Basic 4",
        session_data={...},
        knowledge_id=123,
        education_system="Ghana",
        education_level="Primary"
    )
"""

import logging
from typing import Optional, Dict
from arq import create_pool
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)

# Redis settings - must match curri_worker.py
curri_redis_settings = RedisSettings(
    host="localhost", 
    port=6379, 
    database=4,  # Same as curri_worker.py
    conn_timeout=10, 
    conn_retries=5, 
    conn_retry_delay=1
)


async def enqueue_curriculum_processing(
    teacher_id: str,
    gcs_file_name: str,
    subject: str,
    class_name: str,
    session_data: Dict = None,
    knowledge_id: int = None,
    education_system: str = None,
    education_level: str = None,
    delay: int = 0
):
    """
    Enqueue a curriculum processing task to the ARQ worker queue.
    
    This will trigger the unified processing pipeline:
    1. Text extraction and chunking
    2. Embedding generation
    3. Retrieval from syllabus knowledge base
    4. AI prompt building and processing (with web search)
    5. Storage in Strand/Substrand/ContentStandard/Indicator tables
    
    Args:
        teacher_id: UUID string of the teacher
        gcs_file_name: GCS path to the curriculum file
        subject: Subject name (e.g., "Mathematics")
        class_name: Class name (e.g., "Basic 4")
        session_data: Session data including weekly sessions
        knowledge_id: ID of the KnowledgeMetadata record (optional)
        education_system: Education system (e.g., "Ghana", "Cambridge")
        education_level: Education level (e.g., "Primary", "JHS")
        delay: Delay in seconds before processing starts (default: 0)
    
    Returns:
        Job object with job_id, or None if enqueueing failed
    
    Example:
        job = await enqueue_curriculum_processing(
            teacher_id="7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
            gcs_file_name="curriculum/7bed2b69-8000-4b36-8e91-7fe0b70c9d82/Basic 4/Mathematics.pdf",
            subject="Mathematics",
            class_name="Basic 4",
            session_data=session_data_dict,
            knowledge_id=123,
            education_system="Ghana",
            education_level="Primary"
        )
        print(f"Job ID: {job.job_id}")
    """
    try:
        logger.info(f"📤 Enqueueing curriculum processing for teacher {teacher_id}")
        logger.info(f"   Subject: {subject}, Class: {class_name}")
        logger.info(f"   Education System: {education_system}, Education Level: {education_level}")
        logger.info(f"   GCS File: {gcs_file_name}")
        logger.info(f"   Knowledge ID: {knowledge_id}")
        
        # Create Redis connection pool
        redis = await create_pool(curri_redis_settings)
        
        try:
            # Prepare defer argument if delay is specified
            defer_by = None
            if delay > 0:
                from datetime import timedelta
                defer_by = timedelta(seconds=delay)
                logger.info(f"   Delay: {delay} seconds")
            
            # Enqueue the task with new parameters
            job = await redis.enqueue_job(
                'process_curriculum_task',
                teacher_id,
                gcs_file_name,
                subject,
                class_name,
                session_data,
                knowledge_id,
                education_system,  # New parameter
                education_level,   # New parameter
                _queue_name="curriculum_queue",
                _defer_by=defer_by
            )
            
            logger.info(f"✅ Curriculum processing task enqueued successfully")
            logger.info(f"   Job ID: {job.job_id}")
            
            return job
            
        finally:
            await redis.aclose()
            
    except Exception as e:
        logger.error(f"❌ Failed to enqueue curriculum processing: {e}")
        return None


async def check_strands_exist(
    teacher_id: str,
    subject: str,
    class_name: str
) -> bool:
    """
    Check if strands already exist for a given teacher, subject, and class.
    
    This is used to determine if curriculum processing is needed immediately
    or can be deferred to a scheduler.
    
    Args:
        teacher_id: UUID string of the teacher
        subject: Subject name
        class_name: Class name
    
    Returns:
        True if strands exist, False otherwise
    """
    try:
        from database import get_db
        from model import Strand
        from sqlalchemy import select, and_
        from uuid import UUID
        
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            result = await db.execute(
                select(Strand).where(
                    and_(
                        Strand.teacher_id == UUID(teacher_id),
                        Strand.subject == subject,
                        Strand.class_name == class_name
                    )
                ).limit(1)
            )
            strand = result.scalar_one_or_none()
            
            exists = strand is not None
            logger.info(f"🔍 Strands exist for {subject} - {class_name}: {exists}")
            return exists
            
        finally:
            await db_gen.aclose()
            
    except Exception as e:
        logger.error(f"❌ Error checking strands: {e}")
        return False
