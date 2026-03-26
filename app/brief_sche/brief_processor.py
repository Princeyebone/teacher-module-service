"""
Lesson Brief Processor

Main logic for gathering lesson data and generating briefs.
"""

import os
import sys
import logging
import traceback
import asyncio
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .country_timezone_map import get_timezone_for_country, get_timezone_object
from .brief_prompts import build_lesson_brief_prompt, build_no_session_brief_prompt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create log file
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brief_log.txt")
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

detail_logger = logging.getLogger("brief_detail")
detail_logger.setLevel(logging.INFO)
detail_logger.addHandler(file_handler)
detail_logger.propagate = False


def is_in_generation_window(country: str, window_start: int = 0, window_end: int = 2) -> bool:
    """
    Check if the current local time for a country is in the generation window (12 AM - 2 AM).
    
    Args:
        country: Country name from teacher profile
        window_start: Start hour (default 0 = midnight)
        window_end: End hour (default 2 = 2 AM)
        
    Returns:
        True if current local time is in the generation window
    """
    if not country:
        logger.warning("No country provided, cannot determine timezone")
        return False
    
    tz = get_timezone_object(country)
    if not tz:
        logger.warning(f"Could not get timezone for country: {country}")
        return False
    
    # Get current time in the teacher's timezone
    local_time = datetime.now(tz)
    current_hour = local_time.hour
    
    # Check if in window
    in_window = window_start <= current_hour < window_end
    
    detail_logger.info(f"🕐 Country: {country} | Local time: {local_time.strftime('%H:%M')} | In window: {in_window}")
    
    return in_window


def get_local_date_for_country(country: str) -> date:
    """Get the current local date for a country."""
    tz = get_timezone_object(country)
    if tz:
        return datetime.now(tz).date()
    return datetime.utcnow().date()


async def get_teachers_for_processing() -> List[Dict[str, Any]]:
    """
    Get all teachers from the database.
    
    Returns:
        List of teacher records with id, display_name, and country
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    detail_logger.info("📋 Fetching teachers from database...")
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        result = await db.execute(
            text("""
                SELECT id, display_name, country
                FROM teacherprofile
                WHERE country IS NOT NULL AND country != ''
            """)
        )
        teachers = [dict(row._mapping) for row in result]
        detail_logger.info(f"✅ Found {len(teachers)} teachers with country data")
        return teachers
    finally:
        await db_gen.aclose()


async def get_teacher_subject_classes(teacher_id: UUID) -> List[Dict[str, str]]:
    """
    Get all unique subject + class combinations for a teacher from ClassSession.
    
    Returns:
        List of dicts with 'subject' and 'class_name'
    """
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
        combos = [dict(row._mapping) for row in result]
        return combos
    finally:
        await db_gen.aclose()


async def get_previous_session(
    teacher_id: UUID, 
    subject: str, 
    class_name: str, 
    before_date: date
) -> Optional[Dict[str, Any]]:
    """
    Get the most recent session BEFORE the given date.
    
    Returns:
        Session data or None
    """
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


async def get_todays_session(
    teacher_id: UUID, 
    subject: str, 
    class_name: str, 
    target_date: date
) -> Optional[Dict[str, Any]]:
    """
    Get the session for the given date.
    
    Returns:
        Session data or None
    """
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
                  AND date = :target_date
                LIMIT 1
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name,
                "target_date": target_date
            }
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None
    finally:
        await db_gen.aclose()


async def get_lesson_context_from_session(session_id: int, teacher_id: UUID, subject: str, class_name: str) -> Dict[str, Any]:
    """
    Get strand, substrand, content standard, and indicators linked to a session.
    
    The session info is stored in the session_details JSONB field as:
    [{"id": 1603, "date": "2024-09-11", "end_time": "13:00", "start_time": "12:00", "week_number": 1}]
    
    We need to find indicators where session_details contains an object with matching "id".
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Find indicators linked to this session
        # session_details is an array of objects, we check if any object has id = session_id
        result = await db.execute(
            text("""
                SELECT 
                    i.id as indicator_id,
                    i.indicator_code,
                    i.indicator_text,
                    i.session_details,
                    cs.id as content_standard_id,
                    cs.content_standard_code,
                    cs.content_standard,
                    ss.id as substrand_id,
                    ss.substrand_name,
                    s.id as strand_id,
                    s.strand_name
                FROM indicator i
                JOIN contentstandard cs ON i.content_standard_id = cs.id
                JOIN substrand ss ON cs.substrand_id = ss.id
                JOIN strand s ON ss.strand_id = s.id
                WHERE i.teacher_id = :teacher_id
                  AND i.subject = :subject
                  AND i.class_name = :class_name
                  AND EXISTS (
                      SELECT 1 FROM jsonb_array_elements(i.session_details) AS elem
                      WHERE (elem->>'id')::int = :session_id
                  )
                LIMIT 5
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name,
                "session_id": session_id
            }
        )
        rows = result.fetchall()
        
        detail_logger.info(f"   🔍 Found {len(rows)} indicators linked to session {session_id}")
        
        if not rows:
            return {}
        
        # Take the first row for strand/substrand/content_standard
        first = rows[0]._mapping
        
        # Collect all indicators
        indicators = []
        for row in rows:
            r = row._mapping
            indicators.append({
                "code": r.get("indicator_code", ""),
                "text": r.get("indicator_text", "")
            })
        
        return {
            "strand": first.get("strand_name", ""),
            "substrand": first.get("substrand_name", ""),
            "content_standard": first.get("content_standard", ""),
            "content_standard_code": first.get("content_standard_code", ""),
            "indicators": indicators
        }
        
    finally:
        await db_gen.aclose()


async def get_weekly_activity(
    teacher_id: UUID, 
    subject: str, 
    class_name: str, 
    session_date: date
) -> Dict[str, Any]:
    """
    Get the weekly activity from course_outlines based on session week.
    
    Calculates week number from semester start date, then looks up
    the corresponding week in course_content.
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # First get semester start date
        cal_result = await db.execute(
            text("""
                SELECT semester_start_date
                FROM academiccalendar
                WHERE teacher_id = :teacher_id
                ORDER BY semester_start_date DESC
                LIMIT 1
            """),
            {"teacher_id": str(teacher_id)}
        )
        cal_row = cal_result.fetchone()
        
        if not cal_row:
            detail_logger.warning(f"No academic calendar found for teacher {teacher_id}")
            return {}
        
        semester_start = cal_row._mapping["semester_start_date"]
        
        # Calculate week number (1-indexed)
        days_diff = (session_date - semester_start).days
        week_number = (days_diff // 7) + 1
        
        if week_number < 1:
            week_number = 1
        
        detail_logger.info(f"📅 Session date: {session_date}, Semester start: {semester_start}, Week: {week_number}")
        
        # Get course outline
        outline_result = await db.execute(
            text("""
                SELECT course_content
                FROM course_outlines
                WHERE teacher_id = :teacher_id
                  AND subject_name = :subject
                  AND class_name = :class_name
                ORDER BY updated_at DESC
                LIMIT 1
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name
            }
        )
        outline_row = outline_result.fetchone()
        
        if not outline_row:
            detail_logger.warning(f"No course outline found for {subject} - {class_name}")
            return {}
        
        course_content = outline_row._mapping["course_content"]
        
        if not course_content or not isinstance(course_content, list):
            return {}
        
        # Find the week entry (0-indexed array, but week_number is 1-indexed)
        week_index = week_number - 1
        
        if 0 <= week_index < len(course_content):
            week_data = course_content[week_index]
            return {
                "week_number": week_number,
                "topic": week_data.get("topic", ""),
                "activity": week_data.get("activity", "")
            }
        
        return {"week_number": week_number, "topic": "", "activity": ""}
        
    finally:
        await db_gen.aclose()


async def call_ai_for_brief(prompt: str) -> str:
    """
    Call Vertex AI to generate the lesson brief.
    Uses same pattern as outline_processor.
    """
    from app.core.config import settings
    import time
    import aiohttp
    import json as json_lib
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    
    detail_logger.info("🤖 Calling AI for lesson brief generation...")
    
    # Get access token
    max_auth_retries = 3
    auth_retry_delay = 2
    access_token = None
    
    for auth_attempt in range(max_auth_retries):
        try:
            if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
                service_account_info = json_lib.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
            else:
                with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                    service_account_info = json_lib.load(f)
            
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            credentials.refresh(Request())
            access_token = credentials.token
            break
        except Exception as e:
            if auth_attempt < max_auth_retries - 1:
                time.sleep(auth_retry_delay)
                auth_retry_delay *= 2
            else:
                raise Exception(f"Failed to authenticate: {e}")
    
    if not access_token:
        raise Exception("Failed to obtain access token")
    
    # Call Vertex AI
    project_id = settings.GCS_PROJECT_ID
    model_id = "gemini-2.5-flash"
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
    
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generation_config": {
            "temperature": 0.7,
            "maxOutputTokens": 4096  # Increased to accommodate expanded lesson briefs
        }
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    timeout = aiohttp.ClientTimeout(total=60)
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                response_data = await response.json()
                if "candidates" in response_data and len(response_data["candidates"]) > 0:
                    content = response_data["candidates"][0].get("content", {})
                    if "parts" in content and len(content["parts"]) > 0:
                        ai_response = content["parts"][0].get("text", "").strip()
                        
                        # Log the AI response
                        detail_logger.info("=" * 60)
                        detail_logger.info("AI RESPONSE:")
                        detail_logger.info("=" * 60)
                        detail_logger.info(ai_response)
                        detail_logger.info("=" * 60)
                        
                        return ai_response
            else:
                error_text = await response.text()
                detail_logger.error(f"AI API Error: {error_text[:500]}")
                raise Exception(f"AI API failed with status {response.status}: {error_text[:200]}")
    
    return ""


async def save_lesson_brief(
    teacher_id: UUID,
    subject: str,
    class_name: str,
    session_date: date,
    session_id: Optional[int],
    previous_session_id: Optional[int],
    previous_lesson: Dict[str, Any],
    todays_lesson: Dict[str, Any],
    weekly_activity: Dict[str, Any],
    brief_content: str
):
    """
    Save or update the lesson brief in the database.
    Uses UPSERT for idempotency.
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    detail_logger.info(f"💾 Saving brief for {subject} - {class_name} on {session_date}")
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Use UPSERT (ON CONFLICT UPDATE)
        # Unique key is (teacher_id, subject, class_name) - ONE brief per teacher+subject+class
        # Each new generation updates the existing brief with latest session info
        await db.execute(
            text("""
                INSERT INTO lesson_briefs (
                    teacher_id, subject, class_name, session_date,
                    session_id, previous_session_id,
                    previous_lesson, todays_lesson, weekly_activity,
                    brief_content, generated_at, updated_at, generation_status
                ) VALUES (
                    :teacher_id, :subject, :class_name, :session_date,
                    :session_id, :previous_session_id,
                    :previous_lesson, :todays_lesson, :weekly_activity,
                    :brief_content, :now, :now, 'completed'
                )
                ON CONFLICT (teacher_id, subject, class_name)
                DO UPDATE SET
                    session_date = EXCLUDED.session_date,
                    session_id = EXCLUDED.session_id,
                    previous_session_id = EXCLUDED.previous_session_id,
                    previous_lesson = EXCLUDED.previous_lesson,
                    todays_lesson = EXCLUDED.todays_lesson,
                    weekly_activity = EXCLUDED.weekly_activity,
                    brief_content = EXCLUDED.brief_content,
                    updated_at = EXCLUDED.updated_at,
                    generation_status = 'completed'
            """),
            {
                "teacher_id": str(teacher_id),
                "subject": subject,
                "class_name": class_name,
                "session_date": session_date,
                "session_id": session_id,
                "previous_session_id": previous_session_id,
                "previous_lesson": json.dumps(previous_lesson),
                "todays_lesson": json.dumps(todays_lesson),
                "weekly_activity": json.dumps(weekly_activity),
                "brief_content": brief_content,
                "now": datetime.utcnow()
            }
        )
        await db.commit()
        detail_logger.info("✅ Brief saved successfully")
        
    finally:
        await db_gen.aclose()


async def process_teacher_briefs(teacher_id: UUID, country: str, display_name: Optional[str] = None):
    """
    Process all lesson briefs for a single teacher.
    """
    detail_logger.info(f"\n{'='*60}")
    detail_logger.info(f"👨‍🏫 Processing teacher: {display_name or teacher_id}")
    detail_logger.info(f"   Country: {country}")
    
    # Get local date for the teacher
    local_date = get_local_date_for_country(country)
    detail_logger.info(f"   Local date: {local_date}")
    
    # Get all subject+class combinations
    subject_classes = await get_teacher_subject_classes(teacher_id)
    detail_logger.info(f"   Subject/Class combinations: {len(subject_classes)}")
    
    for sc in subject_classes:
        subject = sc["subject"]
        class_name = sc["class_name"]
        
        detail_logger.info(f"\n📚 Processing: {subject} - {class_name}")
        
        try:
            # Get today's session
            todays_session = await get_todays_session(teacher_id, subject, class_name, local_date)
            
            if not todays_session:
                detail_logger.info(f"   ⏭️ No session today, skipping")
                continue
            
            todays_session_id = todays_session["id"]
            detail_logger.info(f"   📅 Today's session ID: {todays_session_id}")
            
            # Get previous session (before today)
            previous_session = await get_previous_session(teacher_id, subject, class_name, local_date)
            previous_session_id = previous_session["id"] if previous_session else None
            detail_logger.info(f"   📅 Previous session ID: {previous_session_id}")
            
            # Get lesson contexts
            previous_lesson = {}
            if previous_session_id:
                previous_lesson = await get_lesson_context_from_session(
                    previous_session_id, teacher_id, subject, class_name
                )
            detail_logger.info(f"   📖 Previous lesson: {bool(previous_lesson)}")
            
            # Log previous lesson details
            if previous_lesson:
                detail_logger.info("   --- PREVIOUS LESSON DETAILS ---")
                detail_logger.info(f"   Strand: {previous_lesson.get('strand', 'N/A')}")
                detail_logger.info(f"   Substrand: {previous_lesson.get('substrand', 'N/A')}")
                detail_logger.info(f"   Content Standard: {previous_lesson.get('content_standard', 'N/A')}")
                detail_logger.info(f"   Content Standard Code: {previous_lesson.get('content_standard_code', 'N/A')}")
                indicators = previous_lesson.get('indicators', [])
                detail_logger.info(f"   Indicators ({len(indicators)}):")
                for ind in indicators:
                    detail_logger.info(f"      - {ind.get('code', 'N/A')}: {ind.get('text', 'N/A')}")
                detail_logger.info("   -----------------------------------")
            
            todays_lesson = await get_lesson_context_from_session(
                todays_session_id, teacher_id, subject, class_name
            )
            detail_logger.info(f"   📖 Today's lesson: {bool(todays_lesson)}")
            
            # Log today's lesson details
            if todays_lesson:
                detail_logger.info("   --- TODAY'S LESSON DETAILS ---")
                detail_logger.info(f"   Strand: {todays_lesson.get('strand', 'N/A')}")
                detail_logger.info(f"   Substrand: {todays_lesson.get('substrand', 'N/A')}")
                detail_logger.info(f"   Content Standard: {todays_lesson.get('content_standard', 'N/A')}")
                detail_logger.info(f"   Content Standard Code: {todays_lesson.get('content_standard_code', 'N/A')}")
                indicators = todays_lesson.get('indicators', [])
                detail_logger.info(f"   Indicators ({len(indicators)}):")
                for ind in indicators:
                    detail_logger.info(f"      - {ind.get('code', 'N/A')}: {ind.get('text', 'N/A')}")
                detail_logger.info("   ---------------------------------")
            else:
                detail_logger.warning("   ⚠️ No lesson context found for today's session!")
            
            # SKIP if no curriculum data exists for both sessions
            # A meaningful brief requires at least some curriculum data
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
                detail_logger.info(f"   ⏭️ SKIPPING {subject} - {class_name}: No curriculum data linked to previous or current session")
                detail_logger.info(f"      Previous session has data: {has_previous_curriculum}")
                detail_logger.info(f"      Today's session has data: {has_todays_curriculum}")
                continue
            
            detail_logger.info(f"   ✅ Curriculum data found - Previous: {has_previous_curriculum}, Today: {has_todays_curriculum}")
            
            # Get weekly activity
            weekly_activity = await get_weekly_activity(teacher_id, subject, class_name, local_date)
            detail_logger.info(f"   📅 Weekly activity: {weekly_activity.get('week_number', 'N/A')}")
            
            # RAG Retrieval - Get lesson design chunks
            retrieved_chunks = []
            try:
                from .brief_retrieval import retrieve_chunks_for_lesson
                retrieved_chunks = await retrieve_chunks_for_lesson(
                    subject=subject,
                    class_name=class_name,
                    todays_lesson=todays_lesson,
                    limit=2
                )
                detail_logger.info(f"   📚 Retrieved {len(retrieved_chunks)} lesson design chunks")
            except Exception as rag_error:
                detail_logger.warning(f"   RAG retrieval failed: {rag_error}")
            
            # Build prompt
            prompt = build_lesson_brief_prompt(
                subject=subject,
                class_name=class_name,
                previous_lesson=previous_lesson,
                todays_lesson=todays_lesson,
                weekly_activity=weekly_activity,
                teacher_name=display_name,
                retrieved_chunks=retrieved_chunks
            )
            
            # Generate brief
            brief_content = await call_ai_for_brief(prompt)
            detail_logger.info(f"   ✅ Brief generated: {len(brief_content)} chars")
            
            # Save to database
            await save_lesson_brief(
                teacher_id=teacher_id,
                subject=subject,
                class_name=class_name,
                session_date=local_date,
                session_id=todays_session_id,
                previous_session_id=previous_session_id,
                previous_lesson=previous_lesson,
                todays_lesson=todays_lesson,
                weekly_activity=weekly_activity,
                brief_content=brief_content
            )
            
        except Exception as e:
            detail_logger.error(f"   ❌ Error processing {subject} - {class_name}: {e}")
            detail_logger.error(traceback.format_exc())


async def run_brief_generation_cycle():
    """
    Main entry point called by the scheduler.
    Loops through all teachers and generates briefs for those in the time window.
    """
    detail_logger.info("\n" + "="*80)
    detail_logger.info(f"🚀 LESSON BRIEF GENERATION CYCLE STARTED - {datetime.utcnow().isoformat()}")
    detail_logger.info("="*80)
    
    try:
        teachers = await get_teachers_for_processing()
        teachers_processed = 0
        teachers_skipped = 0
        
        for teacher in teachers:
            teacher_id = teacher["id"]
            country = teacher.get("country")
            display_name = teacher.get("display_name")
            
            if not country:
                teachers_skipped += 1
                continue
            
            # Check if teacher is in the generation window
            if is_in_generation_window(country):
                await process_teacher_briefs(UUID(str(teacher_id)), country, display_name)
                teachers_processed += 1
            else:
                teachers_skipped += 1
        
        detail_logger.info("\n" + "="*80)
        detail_logger.info(f"✅ CYCLE COMPLETED")
        detail_logger.info(f"   Teachers processed: {teachers_processed}")
        detail_logger.info(f"   Teachers skipped (not in window): {teachers_skipped}")
        detail_logger.info("="*80 + "\n")
        
    except Exception as e:
        detail_logger.error(f"❌ CYCLE FAILED: {e}")
        detail_logger.error(traceback.format_exc())
        raise


# For testing
if __name__ == "__main__":
    asyncio.run(run_brief_generation_cycle())
