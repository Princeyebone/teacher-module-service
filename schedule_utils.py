"""
Schedule Utilities for TMDL5

This module provides shared utilities for schedule generation and session management.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import select
from model import TeacherProfile, AcademicCalendar, WeeklyTimeTable
from enque_task import enqueue_schedule_generation
from config import settings
import logging

logger = logging.getLogger(__name__)


# Create a separate engine for the utility functions
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True
)


async def trigger_session_generation_if_ready(teacher_id: str, db: AsyncSession):
    """
    Check if both timetable and academic calendar exist for the teacher.
    If both exist, trigger session generation.
    
    This function ensures no duplicate sessions by checking if both required tables have data.
    
    Args:
        teacher_id: UUID string of the teacher
        db: Database session
        
    Returns:
        bool: True if session generation was triggered, False otherwise
    """
    try:
        # Check if academic calendar exists
        academic_calendar_exists = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == teacher_id)
        )).scalar_one_or_none() is not None
        
        # Check if timetable exists
        timetable_exists = (await db.execute(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == teacher_id)
        )).scalars().first() is not None
        
        # If both exist, trigger session generation
        if academic_calendar_exists and timetable_exists:
            # Get teacher profile to get country
            teacher = (await db.execute(
                select(TeacherProfile).where(TeacherProfile.id == teacher_id)
            )).scalar_one_or_none()
            
            if teacher:
                # Enqueue schedule generation
                job_id = await enqueue_schedule_generation(str(teacher_id), teacher.country or "Ghana")
                if job_id:
                    logger.info(f"✅ Session generation triggered for teacher {teacher_id}: {job_id}")
                    return True
                else:
                    logger.error(f"❌ Failed to trigger session generation for teacher {teacher_id}")
                    return False
            else:
                logger.warning(f"⚠️ Teacher profile not found for teacher {teacher_id}")
                return False
        else:
            if not academic_calendar_exists:
                logger.info(f"ℹ️ Academic calendar not found for teacher {teacher_id}, skipping session generation")
            if not timetable_exists:
                logger.info(f"ℹ️ Timetable not found for teacher {teacher_id}, skipping session generation")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error in trigger_session_generation_if_ready for teacher {teacher_id}: {e}")
        # Don't raise exception as this is a background task that shouldn't affect the main flow
        return False


async def check_and_trigger_session_generation(teacher_id: str, db: AsyncSession):
    """
    Public interface for triggering session generation if conditions are met.
    
    Args:
        teacher_id: UUID string of the teacher
        db: Database session
        
    Returns:
        bool: True if session generation was triggered, False otherwise
    """
    return await trigger_session_generation_if_ready(teacher_id, db)


async def trigger_session_generation_after_save(teacher_id: str):
    """
    Trigger session generation after a successful save operation.
    This function creates its own database session to avoid conflicts with the main transaction.
    
    Args:
        teacher_id: UUID string of the teacher
        
    Returns:
        bool: True if session generation was triggered, False otherwise
    """
    logger.info(f"Checking if session generation should be triggered for teacher {teacher_id}")
    
    async with AsyncSession(async_engine) as session:
        try:
            # Check if academic calendar exists
            academic_calendar_exists = (await session.execute(
                select(AcademicCalendar).where(AcademicCalendar.teacher_id == teacher_id)
            )).scalar_one_or_none() is not None
            
            # Check if timetable exists
            timetable_exists = (await session.execute(
                select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == teacher_id)
            )).scalars().first() is not None
            
            # If both exist, trigger session generation
            if academic_calendar_exists and timetable_exists:
                # Get teacher profile to get country
                teacher = (await session.execute(
                    select(TeacherProfile).where(TeacherProfile.id == teacher_id)
                )).scalar_one_or_none()
                
                if teacher:
                    # Enqueue schedule generation
                    job_id = await enqueue_schedule_generation(str(teacher_id), teacher.country or "Ghana")
                    if job_id:
                        logger.info(f"✅ Session generation triggered for teacher {teacher_id}: {job_id}")
                        return True
                    else:
                        logger.error(f"❌ Failed to trigger session generation for teacher {teacher_id}")
                        return False
                else:
                    logger.warning(f"⚠️ Teacher profile not found for teacher {teacher_id}")
                    return False
            else:
                if not academic_calendar_exists:
                    logger.info(f"ℹ️ Academic calendar not found for teacher {teacher_id}, skipping session generation")
                if not timetable_exists:
                    logger.info(f"ℹ️ Timetable not found for teacher {teacher_id}, skipping session generation")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in trigger_session_generation_after_save for teacher {teacher_id}: {e}")
            # Don't raise exception as this is a background task that shouldn't affect the main flow
            return False
        finally:
            await session.close()