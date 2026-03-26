"""
Test Lesson Brief Generation

Run this to immediately test lesson brief generation regardless of time.
Usage: python brief_sche/test_brief_generation.py
"""

import sys
import os
import asyncio
import json
import logging
import traceback
from datetime import datetime, date, timedelta
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.brief_sche.brief_prompts import build_lesson_brief_prompt
from app.brief_sche.brief_processor import (
    call_ai_for_brief,
    save_lesson_brief,
    get_lesson_context_from_session,
    get_weekly_activity,
    detail_logger
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_all_teachers():
    """Get all teachers from database."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        result = await db.execute(
            text("""
                SELECT id, display_name, country
                FROM teacherprofile
                LIMIT 10
            """)
        )
        return [dict(row._mapping) for row in result]
    finally:
        await db_gen.aclose()


async def get_teacher_subjects(teacher_id: UUID):
    """Get unique subject+class combinations for teacher."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        result = await db.execute(
            text("""
                SELECT DISTINCT subject, class_name
                FROM classsession
                WHERE teacher_id = :teacher_id
            """),
            {"teacher_id": str(teacher_id)}
        )
        return [dict(row._mapping) for row in result]
    finally:
        await db_gen.aclose()


async def get_first_two_sessions(teacher_id: UUID, subject: str, class_name: str):
    """
    Get the upcoming session (today or future) and the previous session before it.
    Returns (previous_session, upcoming_session) for proper lesson brief generation.
    
    This now correctly finds the NEXT upcoming session, not the earliest historical ones.
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    today = date.today()
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # First, get the next upcoming session (today or future)
        upcoming_result = await db.execute(
            text("""
                SELECT id, subject, class_name, date, session_number
                FROM classsession
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND class_name = :class_name
                  AND date >= :today
                ORDER BY date ASC, session_number ASC
                LIMIT 1
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name,
                "today": today
            }
        )
        upcoming_row = upcoming_result.fetchone()
        
        if not upcoming_row:
            # No upcoming sessions found
            return None, None
        
        upcoming_session = dict(upcoming_row._mapping)
        upcoming_date = upcoming_session["date"]
        
        # Now get the previous session (before the upcoming session's date)
        previous_result = await db.execute(
            text("""
                SELECT id, subject, class_name, date, session_number
                FROM classsession
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND class_name = :class_name
                  AND date < :upcoming_date
                ORDER BY date DESC, session_number DESC
                LIMIT 1
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name,
                "upcoming_date": upcoming_date
            }
        )
        previous_row = previous_result.fetchone()
        previous_session = dict(previous_row._mapping) if previous_row else None
        
        return previous_session, upcoming_session
        
    finally:
        await db_gen.aclose()


async def get_next_session(teacher_id: UUID, subject: str, class_name: str):
    """Get the next upcoming session (today or future). FOR PRODUCTION USE."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    today = date.today()
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        result = await db.execute(
            text("""
                SELECT id, subject, class_name, date, session_number
                FROM classsession
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND class_name = :class_name
                  AND date >= :today
                ORDER BY date ASC
                LIMIT 1
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name,
                "today": today
            }
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None
    finally:
        await db_gen.aclose()


async def get_previous_session(teacher_id: UUID, subject: str, class_name: str, before_date: date):
    """Get the most recent session before the given date."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        result = await db.execute(
            text("""
                SELECT id, subject, class_name, date, session_number
                FROM classsession
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND class_name = :class_name
                  AND date < :before_date
                ORDER BY date DESC
                LIMIT 1
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name,
                "before_date": before_date
            }
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None
    finally:
        await db_gen.aclose()


async def test_single_teacher_brief(teacher_id: str, teacher_name: str = None):
    """Test brief generation for a single teacher."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"👨‍🏫 Testing teacher: {teacher_name or teacher_id}")
    logger.info(f"{'='*60}")
    
    teacher_uuid = UUID(teacher_id)
    
    # Get all subject+class combinations
    subject_classes = await get_teacher_subjects(teacher_uuid)
    
    if not subject_classes:
        logger.warning("❌ No subject/class combinations found for this teacher")
        return
    
    logger.info(f"📚 Found {len(subject_classes)} subject/class combinations")
    
    for sc in subject_classes:
        subject = sc["subject"]
        class_name = sc["class_name"]
        
        logger.info(f"\n📖 Processing: {subject} - {class_name}")
        
        try:
            # FOR TESTING: Get first two sessions (ignore current date)
            # First session = "previous lesson", Second session = "today's lesson"
            prev_session, todays_session = await get_first_two_sessions(teacher_uuid, subject, class_name)
            
            if not todays_session:
                logger.warning(f"   ❌ No sessions found at all")
                continue
            
            todays_session_id = todays_session["id"]
            session_date = todays_session["date"]
            prev_session_id = prev_session["id"] if prev_session else None
            
            logger.info(f"   📅 Upcoming session: ID={todays_session_id}, Date={session_date}")
            logger.info(f"   📅 Previous session: {prev_session_id or 'None (first class)'}")
            
            # Get lesson contexts
            previous_lesson = {}
            if prev_session_id:
                previous_lesson = await get_lesson_context_from_session(
                    prev_session_id, teacher_uuid, subject, class_name
                )
            logger.info(f"   📖 Previous lesson context: {'Yes' if previous_lesson else 'No'}")
            if previous_lesson:
                logger.info(f"      --- PREVIOUS LESSON DETAILS ---")
                logger.info(f"      Strand: {previous_lesson.get('strand', 'N/A')}")
                logger.info(f"      Substrand: {previous_lesson.get('substrand', 'N/A')}")
                logger.info(f"      Content Standard: {previous_lesson.get('content_standard', 'N/A')}")
                logger.info(f"      Content Standard Code: {previous_lesson.get('content_standard_code', 'N/A')}")
                indicators = previous_lesson.get('indicators', [])
                logger.info(f"      Indicators ({len(indicators)}):")
                for ind in indicators:
                    logger.info(f"         - {ind.get('code', 'N/A')}: {ind.get('text', 'N/A')}")
                logger.info(f"      ---------------------------------")
            
            todays_lesson = await get_lesson_context_from_session(
                todays_session_id, teacher_uuid, subject, class_name
            )
            logger.info(f"   📖 Today's lesson context: {'Yes' if todays_lesson else 'No'}")
            if todays_lesson:
                logger.info(f"      --- TODAY'S LESSON DETAILS ---")
                logger.info(f"      Strand: {todays_lesson.get('strand', 'N/A')}")
                logger.info(f"      Substrand: {todays_lesson.get('substrand', 'N/A')}")
                logger.info(f"      Content Standard: {todays_lesson.get('content_standard', 'N/A')}")
                logger.info(f"      Content Standard Code: {todays_lesson.get('content_standard_code', 'N/A')}")
                indicators = todays_lesson.get('indicators', [])
                logger.info(f"      Indicators ({len(indicators)}):")
                for ind in indicators:
                    logger.info(f"         - {ind.get('code', 'N/A')}: {ind.get('text', 'N/A')}")
                logger.info(f"      ---------------------------------")
            else:
                logger.warning(f"      ⚠️ No lesson context found for today's session!")
            
            # SKIP if no curriculum data exists for both sessions
            has_previous_curriculum = bool(previous_lesson and (
                previous_lesson.get('strand') or 
                previous_lesson.get('substrand') or 
                previous_lesson.get('content_standard') or 
                previous_lesson.get('indicators')
            ))
            has_todays_curriculum = bool(todays_lesson and (
                todays_lesson.get('strand') or 
                todays_lesson.get('substrand') or 
                todays_lesson.get('content_standard') or 
                todays_lesson.get('indicators')
            ))
            
            if not has_previous_curriculum and not has_todays_curriculum:
                logger.info(f"   ⏭️ SKIPPING {subject} - {class_name}: No curriculum data linked to sessions")
                continue
            
            logger.info(f"   ✅ Curriculum data found - Previous: {has_previous_curriculum}, Today: {has_todays_curriculum}")
            
            # Get weekly activity
            weekly_activity = await get_weekly_activity(teacher_uuid, subject, class_name, session_date)
            logger.info(f"   📅 Weekly activity: Week {weekly_activity.get('week_number', 'N/A')}")
            if weekly_activity.get("topic"):
                logger.info(f"      Topic: {weekly_activity.get('topic', 'N/A')[:50]}...")
            
            # RAG Retrieval - Get lesson design chunks
            logger.info(f"   🔍 Retrieving lesson design chunks...")
            retrieved_chunks = []
            try:
                from app.brief_sche.brief_retrieval import retrieve_chunks_for_lesson
                retrieved_chunks = await retrieve_chunks_for_lesson(
                    subject=subject,
                    class_name=class_name,
                    todays_lesson=todays_lesson,
                    limit=2
                )
                logger.info(f"   📚 Retrieved {len(retrieved_chunks)} lesson design chunks")
                for i, chunk in enumerate(retrieved_chunks):
                    logger.info(f"      Chunk {i+1}: similarity={chunk.get('similarity', 'N/A')}")
            except Exception as rag_error:
                logger.warning(f"   ⚠️ RAG retrieval failed (continuing without): {rag_error}")
            
            # Build prompt
            logger.info(f"   🔨 Building prompt...")
            prompt = build_lesson_brief_prompt(
                subject=subject,
                class_name=class_name,
                previous_lesson=previous_lesson,
                todays_lesson=todays_lesson,
                weekly_activity=weekly_activity,
                teacher_name=teacher_name,
                retrieved_chunks=retrieved_chunks
            )
            logger.info(f"   📝 Prompt length: {len(prompt)} characters")
            
            # Call AI
            logger.info(f"   🤖 Calling AI for lesson brief...")
            brief_content = await call_ai_for_brief(prompt)
            logger.info(f"   ✅ Brief generated: {len(brief_content)} characters")
            
            # Print a preview
            logger.info(f"\n   📋 BRIEF PREVIEW:")
            logger.info("-" * 50)
            preview = brief_content[:500] + "..." if len(brief_content) > 500 else brief_content
            for line in preview.split("\n"):
                logger.info(f"   {line}")
            logger.info("-" * 50)
            
            # Save to database
            logger.info(f"   💾 Saving to database...")
            await save_lesson_brief(
                teacher_id=teacher_uuid,
                subject=subject,
                class_name=class_name,
                session_date=session_date,
                session_id=todays_session_id,
                previous_session_id=prev_session_id,
                previous_lesson=previous_lesson,
                todays_lesson=todays_lesson,
                weekly_activity=weekly_activity,
                brief_content=brief_content
            )
            logger.info(f"   ✅ SAVED SUCCESSFULLY!")
            
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
            logger.error(traceback.format_exc())


async def run_test():
    """Main test function."""
    logger.info("\n" + "=" * 70)
    logger.info("  LESSON BRIEF GENERATION TEST")
    logger.info("  Running immediately regardless of timezone")
    logger.info("=" * 70)
    
    # Get all teachers
    teachers = await get_all_teachers()
    
    if not teachers:
        logger.error("❌ No teachers found in database!")
        return
    
    logger.info(f"\n📋 Found {len(teachers)} teachers")
    
    for i, teacher in enumerate(teachers):
        logger.info(f"  {i+1}. {teacher.get('display_name', 'Unknown')} ({teacher['id']})")
    
    # Process first teacher with data (you can modify this)
    for teacher in teachers:
        teacher_id = str(teacher["id"])
        teacher_name = teacher.get("display_name", "Unknown Teacher")
        
        await test_single_teacher_brief(teacher_id, teacher_name)
        
        # Process all teachers (no break)
    
    logger.info("\n" + "=" * 70)
    logger.info("  TEST COMPLETED")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_test())
