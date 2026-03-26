"""
Weekly Lesson Note Processor

Main logic for gathering lesson data and generating weekly lesson notes.
Includes retry mechanism with exponential backoff for AI and DB operations.
"""

import os
import sys
import logging
import traceback
import asyncio
import json
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

import pytz
import aiohttp

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create log file
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lesson_note_log.txt")
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

detail_logger = logging.getLogger("lesson_note_detail")
detail_logger.setLevel(logging.INFO)
detail_logger.addHandler(file_handler)
detail_logger.propagate = False


# ============================================================================
# TIMEZONE UTILITIES
# ============================================================================

# Country to timezone mapping (same as brief_sche)
COUNTRY_TIMEZONE_MAP = {
    # Africa
    "ghana": "Africa/Accra",
    "nigeria": "Africa/Lagos",
    "kenya": "Africa/Nairobi",
    "south africa": "Africa/Johannesburg",
    "egypt": "Africa/Cairo",
    "morocco": "Africa/Casablanca",
    "tanzania": "Africa/Dar_es_Salaam",
    "uganda": "Africa/Kampala",
    "ethiopia": "Africa/Addis_Ababa",
    "cameroon": "Africa/Douala",
    "ivory coast": "Africa/Abidjan",
    "senegal": "Africa/Dakar",
    "zimbabwe": "Africa/Harare",
    "zambia": "Africa/Lusaka",
    "rwanda": "Africa/Kigali",
    
    # Europe
    "united kingdom": "Europe/London",
    "uk": "Europe/London",
    "germany": "Europe/Berlin",
    "france": "Europe/Paris",
    "spain": "Europe/Madrid",
    "italy": "Europe/Rome",
    "netherlands": "Europe/Amsterdam",
    "belgium": "Europe/Brussels",
    "poland": "Europe/Warsaw",
    "portugal": "Europe/Lisbon",
    "ireland": "Europe/Dublin",
    
    # Americas
    "united states": "America/New_York",
    "usa": "America/New_York",
    "canada": "America/Toronto",
    "brazil": "America/Sao_Paulo",
    "mexico": "America/Mexico_City",
    "argentina": "America/Buenos_Aires",
    "colombia": "America/Bogota",
    "chile": "America/Santiago",
    
    # Asia
    "india": "Asia/Kolkata",
    "china": "Asia/Shanghai",
    "japan": "Asia/Tokyo",
    "south korea": "Asia/Seoul",
    "singapore": "Asia/Singapore",
    "malaysia": "Asia/Kuala_Lumpur",
    "thailand": "Asia/Bangkok",
    "indonesia": "Asia/Jakarta",
    "philippines": "Asia/Manila",
    "vietnam": "Asia/Ho_Chi_Minh",
    "pakistan": "Asia/Karachi",
    "bangladesh": "Asia/Dhaka",
    "uae": "Asia/Dubai",
    "saudi arabia": "Asia/Riyadh",
    
    # Oceania
    "australia": "Australia/Sydney",
    "new zealand": "Pacific/Auckland",
}


def get_timezone_for_country(country: str) -> str:
    """Get timezone string for a country."""
    if not country:
        return "UTC"
    country_lower = country.lower().strip()
    return COUNTRY_TIMEZONE_MAP.get(country_lower, "UTC")


def get_timezone_object(country: str):
    """Get pytz timezone object for a country."""
    tz_str = get_timezone_for_country(country)
    try:
        return pytz.timezone(tz_str)
    except Exception:
        return pytz.UTC


def is_in_generation_window(country: str) -> bool:
    """
    Check if the current local time for a country is in the generation window.
    Window: Wednesday 12 AM - 2 AM OR Thursday 12 AM - 2 AM
    
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
    current_weekday = local_time.weekday()  # Monday=0, Tuesday=1, Wednesday=2, Thursday=3
    
    # Check if Wednesday (2) or Thursday (3) between 12 AM and 2 AM (hours 0-1)
    is_wed_or_thu = current_weekday in [2, 3]
    is_in_time_window = 0 <= current_hour < 2
    
    in_window = is_wed_or_thu and is_in_time_window
    
    day_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][current_weekday]
    detail_logger.info(f"🕐 Country: {country} | Day: {day_name} | Local time: {local_time.strftime('%H:%M')} | In window: {in_window}")
    
    return in_window


def get_local_date_for_country(country: str) -> date:
    """Get the current local date for a country."""
    tz = get_timezone_object(country)
    if tz:
        return datetime.now(tz).date()
    return datetime.utcnow().date()


def get_current_week_friday(country: str) -> date:
    """
    Get the Friday date of the CURRENT week for the given country.
    Lesson notes are made for the coming week but use the current week's Friday date.
    """
    tz = get_timezone_object(country)
    local_date = datetime.now(tz).date() if tz else datetime.utcnow().date()
    
    # Get the weekday (Monday=0, Sunday=6)
    current_weekday = local_date.weekday()
    
    # Calculate days until Friday (Friday=4)
    days_until_friday = (4 - current_weekday) % 7
    if days_until_friday < 0:
        days_until_friday += 7
    
    friday_date = local_date + timedelta(days=days_until_friday)
    
    # If we're past Friday (Saturday or Sunday), use the previous Friday
    if current_weekday > 4:
        friday_date = local_date - timedelta(days=(current_weekday - 4))
    
    return friday_date


def get_coming_week_dates(country: str) -> Tuple[date, date]:
    """
    Get the date range for the COMING week.
    The coming week starts on the Monday after the current week's Friday.
    
    Returns:
        Tuple of (week_start, week_end) where week_start is Monday and week_end is Sunday
    """
    current_friday = get_current_week_friday(country)
    
    # Coming week starts 3 days after Friday (Monday)
    coming_week_start = current_friday + timedelta(days=3)
    coming_week_end = coming_week_start + timedelta(days=6)  # Sunday
    
    return coming_week_start, coming_week_end


# ============================================================================
# RETRY UTILITIES
# ============================================================================

class RetryableError(Exception):
    """Exception indicating an operation can be retried."""
    pass


async def retry_with_backoff(
    operation,
    max_retries: int = 5,
    initial_delay: float = 2.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0,
    operation_name: str = "operation"
):
    """
    Execute an async operation with exponential backoff retry.
    
    Args:
        operation: Async callable to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_multiplier: Multiplier for each retry
        operation_name: Name for logging purposes
        
    Returns:
        Result of the operation
        
    Raises:
        Exception: If all retries fail
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            result = await operation()
            if attempt > 0:
                detail_logger.info(f"✅ {operation_name} succeeded on attempt {attempt + 1}")
            return result
            
        except aiohttp.ClientError as e:
            last_exception = e
            detail_logger.warning(f"⚠️ Network error in {operation_name} (attempt {attempt + 1}/{max_retries + 1}): {e}")
            
        except Exception as e:
            error_str = str(e).lower()
            
            # NON-retryable errors (fail fast)
            is_non_retryable = any([
                "invalid_grant" in error_str,  # Clock skew - won't fix with retry
                "invalid jwt" in error_str,    # JWT issues - won't fix with retry
                "permission denied" in error_str,
                "not found" in error_str,
                "invalid argument" in error_str,
            ])
            
            if is_non_retryable:
                detail_logger.error(f"❌ Non-retryable error in {operation_name}: {e}")
                raise e
            
            # Check for retryable errors
            is_retryable = any([
                "rate limit" in error_str,
                "quota" in error_str,
                "429" in error_str,
                "503" in error_str,
                "500" in error_str,
                "timeout" in error_str,
                "connection" in error_str,
                "database" in error_str or "db" in error_str,
                "deadlock" in error_str,
                "connection refused" in error_str,
                "temporarily unavailable" in error_str,
            ])
            
            if is_retryable and attempt < max_retries:
                last_exception = e
                detail_logger.warning(f"⚠️ Retryable error in {operation_name} (attempt {attempt + 1}/{max_retries + 1}): {e}")
            else:
                # Non-retryable error or last attempt
                raise e
        
        if attempt < max_retries:
            detail_logger.info(f"⏳ Waiting {delay:.1f}s before retry...")
            await asyncio.sleep(delay)
            delay = min(delay * backoff_multiplier, max_delay)
    
    # All retries exhausted
    raise last_exception or Exception(f"{operation_name} failed after {max_retries + 1} attempts")


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

async def get_all_teachers() -> List[Dict[str, Any]]:
    """Get all teachers from the database."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    detail_logger.info("📋 Fetching teachers from database...")
    
    async def _fetch():
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
            return [dict(row._mapping) for row in result]
        finally:
            await db_gen.aclose()
    
    teachers = await retry_with_backoff(_fetch, operation_name="fetch_teachers")
    detail_logger.info(f"✅ Found {len(teachers)} teachers with country data")
    return teachers


async def get_teacher_subject_classes(teacher_id: UUID) -> List[Dict[str, str]]:
    """Get all unique subject + class combinations for a teacher."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    async def _fetch():
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
    
    return await retry_with_backoff(_fetch, operation_name="fetch_subject_classes")


async def get_indicators_for_coming_week(
    teacher_id: UUID,
    subject: str,
    class_name: str,
    week_start: date,
    week_end: date
) -> List[Dict[str, Any]]:
    """
    Get all indicators that have sessions scheduled in the coming week.
    
    Returns list of dicts with indicator info and session details.
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    async def _fetch():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            # Get indicators whose session_details contain sessions in the coming week
            result = await db.execute(
                text("""
                    SELECT DISTINCT ON (i.id)
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
                          WHERE (elem->>'date')::date BETWEEN :week_start AND :week_end
                      )
                    ORDER BY i.id
                """),
                {
                    "teacher_id": str(teacher_id),
                    "subject": subject,
                    "class_name": class_name,
                    "week_start": week_start,
                    "week_end": week_end
                }
            )
            return [dict(row._mapping) for row in result]
        finally:
            await db_gen.aclose()
    
    return await retry_with_backoff(_fetch, operation_name="fetch_indicators_for_week")


async def get_duration_from_timetable(
    teacher_id: UUID,
    subject: str,
    class_name: str
) -> str:
    """Get duration (start_time - end_time) from weekly timetable."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    async def _fetch():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            result = await db.execute(
                text("""
                    SELECT start_time, end_time
                    FROM weeklytimetable
                    WHERE teacher_id = :teacher_id
                      AND subject = :subject
                      AND (pupils = :class_name OR pupils ILIKE :class_pattern)
                    LIMIT 1
                """),
                {
                    "teacher_id": str(teacher_id),
                    "subject": subject,
                    "class_name": class_name,
                    "class_pattern": f"%{class_name}%"
                }
            )
            row = result.fetchone()
            if row:
                mapping = row._mapping
                start = mapping.get("start_time")
                end = mapping.get("end_time")
                if start and end:
                    # Format time objects to string
                    start_str = start.strftime("%H:%M") if hasattr(start, 'strftime') else str(start)
                    end_str = end.strftime("%H:%M") if hasattr(end, 'strftime') else str(end)
                    return f"{start_str} - {end_str}"
            return ""
        finally:
            await db_gen.aclose()
    
    return await retry_with_backoff(_fetch, operation_name="fetch_duration")


async def get_semester_info(teacher_id: UUID) -> Dict[str, Any]:
    """Get current semester info from academic calendar."""
    from app.core.database import get_db
    from sqlalchemy import text
    
    async def _fetch():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            result = await db.execute(
                text("""
                    SELECT semester_name, semester_start_date, semester_end_date
                    FROM academiccalendar
                    WHERE teacher_id = :teacher_id
                    ORDER BY semester_start_date DESC
                    LIMIT 1
                """),
                {"teacher_id": str(teacher_id)}
            )
            row = result.fetchone()
            if row:
                return dict(row._mapping)
            return {}
        finally:
            await db_gen.aclose()
    
    return await retry_with_backoff(_fetch, operation_name="fetch_semester_info")


def calculate_week_number(session_date: date, semester_start: date) -> int:
    """Calculate week number from semester start date."""
    if not semester_start:
        return 1
    days_diff = (session_date - semester_start).days
    week_number = (days_diff // 7) + 1
    return max(1, week_number)


async def save_lesson_note(
    teacher_id: UUID,
    subject: str,
    class_name: str,
    indicator_id: int,
    week_date: date,
    duration: str,
    strand: str,
    substrand: str,
    content_standard: str,
    content_standard_code: str,
    indicator_text: str,
    indicator_code: str,
    week_number: int,
    semester_name: str,
    lesson_number: str,
    performance_indicator: str,
    core_competency: str,
    reference_page: str,
    phase1_activity: str,
    phase1_resources: str,
    phase2_activity: str,
    phase2_resources: str,
    phase3_activity: str,
    phase3_resources: str
):
    """
    Save or update the lesson note in the database.
    Uses UPSERT for idempotency.
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    detail_logger.info(f"💾 Saving lesson note for {subject} - {class_name}")
    
    async def _save():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            await db.execute(
                text("""
                    INSERT INTO weekly_lesson_notes (
                        teacher_id, subject, class_name, indicator_id, week_date,
                        duration, strand, substrand, content_standard, content_standard_code,
                        indicator_text, indicator_code, week_number, semester_name,
                        lesson_number, performance_indicator, core_competency, reference_page,
                        phase1_activity, phase1_resources, phase2_activity, phase2_resources,
                        phase3_activity, phase3_resources, generated_at, updated_at, generation_status
                    ) VALUES (
                        :teacher_id, :subject, :class_name, :indicator_id, :week_date,
                        :duration, :strand, :substrand, :content_standard, :content_standard_code,
                        :indicator_text, :indicator_code, :week_number, :semester_name,
                        :lesson_number, :performance_indicator, :core_competency, :reference_page,
                        :phase1_activity, :phase1_resources, :phase2_activity, :phase2_resources,
                        :phase3_activity, :phase3_resources, :now, :now, 'completed'
                    )
                    ON CONFLICT (teacher_id, subject, class_name, indicator_id, week_date)
                    DO UPDATE SET
                        duration = EXCLUDED.duration,
                        strand = EXCLUDED.strand,
                        substrand = EXCLUDED.substrand,
                        content_standard = EXCLUDED.content_standard,
                        content_standard_code = EXCLUDED.content_standard_code,
                        indicator_text = EXCLUDED.indicator_text,
                        indicator_code = EXCLUDED.indicator_code,
                        week_number = EXCLUDED.week_number,
                        semester_name = EXCLUDED.semester_name,
                        lesson_number = EXCLUDED.lesson_number,
                        performance_indicator = EXCLUDED.performance_indicator,
                        core_competency = EXCLUDED.core_competency,
                        reference_page = EXCLUDED.reference_page,
                        phase1_activity = EXCLUDED.phase1_activity,
                        phase1_resources = EXCLUDED.phase1_resources,
                        phase2_activity = EXCLUDED.phase2_activity,
                        phase2_resources = EXCLUDED.phase2_resources,
                        phase3_activity = EXCLUDED.phase3_activity,
                        phase3_resources = EXCLUDED.phase3_resources,
                        updated_at = EXCLUDED.updated_at,
                        generation_status = 'completed'
                """),
                {
                    "teacher_id": str(teacher_id),
                    "subject": subject,
                    "class_name": class_name,
                    "indicator_id": indicator_id,
                    "week_date": week_date,
                    "duration": duration,
                    "strand": strand,
                    "substrand": substrand,
                    "content_standard": content_standard,
                    "content_standard_code": content_standard_code,
                    "indicator_text": indicator_text,
                    "indicator_code": indicator_code,
                    "week_number": week_number,
                    "semester_name": semester_name,
                    "lesson_number": lesson_number,
                    "performance_indicator": performance_indicator,
                    "core_competency": core_competency,
                    "reference_page": reference_page,
                    "phase1_activity": phase1_activity,
                    "phase1_resources": phase1_resources,
                    "phase2_activity": phase2_activity,
                    "phase2_resources": phase2_resources,
                    "phase3_activity": phase3_activity,
                    "phase3_resources": phase3_resources,
                    "now": datetime.utcnow()
                }
            )
            await db.commit()
            detail_logger.info("✅ Lesson note saved successfully")
        finally:
            await db_gen.aclose()
    
    await retry_with_backoff(_save, operation_name="save_lesson_note")


# ============================================================================
# AI OPERATIONS
# ============================================================================

async def call_ai_with_retry(prompt: str, operation_name: str = "AI call") -> str:
    """
    Call Vertex AI with retry mechanism.
    Uses same authentication pattern as other modules.
    """
    from app.core.config import settings
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    
    async def _call_ai():
        # Get access token
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            service_account_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                service_account_info = json.load(f)
        
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        credentials.refresh(Request())
        access_token = credentials.token
        
        # Call Vertex AI
        project_id = settings.GCS_PROJECT_ID
        model_id = "gemini-2.5-flash"
        url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
        
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generation_config": {
                "temperature": 0.7,
                "maxOutputTokens": 4096
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
                            return content["parts"][0].get("text", "").strip()
                else:
                    error_text = await response.text()
                    raise Exception(f"AI API failed with status {response.status}: {error_text[:200]}")
        
        return ""
    
    return await retry_with_backoff(_call_ai, operation_name=operation_name)


async def generate_performance_indicator_and_competency(
    subject: str,
    class_name: str,
    semester_name: str,
    strand: str,
    substrand: str,
    content_standard: str,
    indicator_text: str,
    country: str
) -> Dict[str, str]:
    """Generate performance indicator and core competency using AI."""
    from .note_prompts import build_performance_indicator_prompt, parse_performance_indicator_response
    
    detail_logger.info(f"      🤖 AI: Generating performance indicator for {subject} - {class_name}...")
    
    prompt = build_performance_indicator_prompt(
        subject=subject,
        class_name=class_name,
        semester_name=semester_name,
        strand=strand,
        substrand=substrand,
        content_standard=content_standard,
        indicator_text=indicator_text,
        country=country
    )
    
    ai_response = await call_ai_with_retry(prompt, "generate_performance_indicator")
    result = parse_performance_indicator_response(ai_response)
    
    detail_logger.info(f"      ✅ AI: Performance indicator generated successfully")
    return result


async def generate_learner_activities(
    subject: str,
    class_name: str,
    semester_name: str,
    strand: str,
    substrand: str,
    content_standard: str,
    indicator_text: str,
    country: str,
    performance_indicator: str = ""
) -> Dict[str, Dict[str, str]]:
    """Generate learner activities and resources for all phases using AI."""
    from .note_prompts import build_learner_activities_prompt, parse_learner_activities_response, DEFAULT_PHASE_ACTIVITIES
    
    detail_logger.info(f"      🤖 AI: Generating learner activities for {subject} - {class_name}...")
    
    prompt = build_learner_activities_prompt(
        subject=subject,
        class_name=class_name,
        semester_name=semester_name,
        strand=strand,
        substrand=substrand,
        content_standard=content_standard,
        indicator_text=indicator_text,
        country=country,
        performance_indicator=performance_indicator
    )
    
    ai_response = await call_ai_with_retry(prompt, "generate_learner_activities")
    result = parse_learner_activities_response(ai_response)
    
    # Use defaults for any missing phases
    for phase in ['phase1', 'phase2', 'phase3']:
        if not result[phase]["activity"]:
            result[phase] = DEFAULT_PHASE_ACTIVITIES[phase]
    
    detail_logger.info(f"      ✅ AI: Learner activities generated successfully")
    return result


# ============================================================================
# MAIN PROCESSING LOGIC
# ============================================================================

async def process_teacher_lesson_notes(teacher_id: UUID, country: str, display_name: Optional[str] = None):
    """
    Process all weekly lesson notes for a single teacher.
    """
    detail_logger.info(f"\n{'='*60}")
    detail_logger.info(f"👨‍🏫 Processing teacher: {display_name or teacher_id}")
    detail_logger.info(f"   Country: {country}")
    
    # Get dates
    week_friday = get_current_week_friday(country)
    coming_week_start, coming_week_end = get_coming_week_dates(country)
    
    detail_logger.info(f"   📅 CURRENT week's Friday (stored as week_date): {week_friday}")
    detail_logger.info(f"   📅 COMING week range (indicator search): {coming_week_start} to {coming_week_end}")
    detail_logger.info(f"   ℹ️ Building lesson notes FOR the coming week, stored with current Friday date")
    
    # Get semester info
    semester_info = await get_semester_info(teacher_id)
    semester_name = semester_info.get("semester_name", "")
    semester_start = semester_info.get("semester_start_date")
    
    if not semester_name:
        detail_logger.warning(f"   ⚠️ No semester info found, using defaults")
    
    # Calculate week number based on COMING week (the week the lesson is FOR)
    # NOT based on current Friday (which is when the note is made)
    week_number = calculate_week_number(coming_week_start, semester_start)
    detail_logger.info(f"   Week number (for coming week): {week_number}")
    
    # Get all subject+class combinations
    subject_classes = await get_teacher_subject_classes(teacher_id)
    detail_logger.info(f"   Subject/Class combinations: {len(subject_classes)}")
    
    if not subject_classes:
        detail_logger.info(f"   ⏭️ No subject/class combinations, skipping teacher")
        return
    
    for sc in subject_classes:
        subject = sc["subject"]
        class_name = sc["class_name"]
        
        detail_logger.info(f"\n📚 Processing: {subject} - {class_name}")
        
        try:
            # Get indicators for the coming week
            indicators = await get_indicators_for_coming_week(
                teacher_id, subject, class_name, coming_week_start, coming_week_end
            )
            
            if not indicators:
                detail_logger.info(f"   ⏭️ No indicators for coming week, skipping")
                continue
            
            total_indicators = len(indicators)
            detail_logger.info(f"   📊 Found {total_indicators} indicators for coming week")
            
            # Get duration from timetable
            duration = await get_duration_from_timetable(teacher_id, subject, class_name)
            detail_logger.info(f"   ⏱️ Duration: {duration or 'Not found'}")
            
            # Process each indicator
            for idx, indicator in enumerate(indicators, 1):
                try:
                    indicator_id = indicator["indicator_id"]
                    indicator_text = indicator.get("indicator_text", "")
                    indicator_code = indicator.get("indicator_code", "")
                    strand = indicator.get("strand_name", "")
                    substrand = indicator.get("substrand_name", "")
                    content_standard = indicator.get("content_standard", "")
                    content_standard_code = indicator.get("content_standard_code", "")
                    
                    lesson_number = f"{idx} of {total_indicators}"
                    reference_page = f"{subject} curriculum"
                    
                    detail_logger.info(f"   📝 Processing indicator {idx}/{total_indicators}: {indicator_code or 'No code'}")
                    
                    # Generate performance indicator and core competency
                    perf_data = await generate_performance_indicator_and_competency(
                        subject=subject,
                        class_name=class_name,
                        semester_name=semester_name,
                        strand=strand,
                        substrand=substrand,
                        content_standard=content_standard,
                        indicator_text=indicator_text,
                        country=country
                    )
                    
                    performance_indicator = perf_data.get("performance_indicator", "")
                    core_competency = perf_data.get("core_competency", "")
                    
                    # Generate learner activities and resources
                    activities = await generate_learner_activities(
                        subject=subject,
                        class_name=class_name,
                        semester_name=semester_name,
                        strand=strand,
                        substrand=substrand,
                        content_standard=content_standard,
                        indicator_text=indicator_text,
                        country=country,
                        performance_indicator=performance_indicator
                    )
                    
                    # Save to database
                    await save_lesson_note(
                        teacher_id=teacher_id,
                        subject=subject,
                        class_name=class_name,
                        indicator_id=indicator_id,
                        week_date=week_friday,
                        duration=duration,
                        strand=strand,
                        substrand=substrand,
                        content_standard=content_standard,
                        content_standard_code=content_standard_code,
                        indicator_text=indicator_text,
                        indicator_code=indicator_code,
                        week_number=week_number,
                        semester_name=semester_name,
                        lesson_number=lesson_number,
                        performance_indicator=performance_indicator,
                        core_competency=core_competency,
                        reference_page=reference_page,
                        phase1_activity=activities["phase1"]["activity"],
                        phase1_resources=activities["phase1"]["resources"],
                        phase2_activity=activities["phase2"]["activity"],
                        phase2_resources=activities["phase2"]["resources"],
                        phase3_activity=activities["phase3"]["activity"],
                        phase3_resources=activities["phase3"]["resources"]
                    )
                    
                    detail_logger.info(f"   ✅ Lesson note {idx}/{total_indicators} saved")
                    
                except Exception as e:
                    detail_logger.error(f"   ❌ Error processing indicator {idx}: {e}")
                    detail_logger.error(traceback.format_exc())
            
        except Exception as e:
            detail_logger.error(f"   ❌ Error processing {subject} - {class_name}: {e}")
            detail_logger.error(traceback.format_exc())


async def run_lesson_note_generation_cycle():
    """
    Main entry point called by the scheduler.
    Loops through all teachers and generates lesson notes for those in the time window.
    """
    detail_logger.info("\n" + "=" * 80)
    detail_logger.info(f"🚀 WEEKLY LESSON NOTE GENERATION CYCLE STARTED - {datetime.utcnow().isoformat()}")
    detail_logger.info("=" * 80)
    
    try:
        teachers = await get_all_teachers()
        teachers_processed = 0
        teachers_skipped = 0
        
        for teacher in teachers:
            teacher_id = teacher["id"]
            country = teacher.get("country")
            display_name = teacher.get("display_name")
            
            if not country:
                teachers_skipped += 1
                continue
            
            # Check if teacher is in the generation window (Wed/Thu 12-2 AM)
            if is_in_generation_window(country):
                await process_teacher_lesson_notes(UUID(str(teacher_id)), country, display_name)
                teachers_processed += 1
            else:
                teachers_skipped += 1
        
        detail_logger.info("\n" + "=" * 80)
        detail_logger.info(f"✅ CYCLE COMPLETED")
        detail_logger.info(f"   Teachers processed: {teachers_processed}")
        detail_logger.info(f"   Teachers skipped (not in window): {teachers_skipped}")
        detail_logger.info("=" * 80 + "\n")
        
    except Exception as e:
        detail_logger.error(f"❌ CYCLE FAILED: {e}")
        detail_logger.error(traceback.format_exc())
        raise


# For testing
if __name__ == "__main__":
    asyncio.run(run_lesson_note_generation_cycle())
