"""
Slide Processor

Main logic for slide generation, validation, and persistence.
Scheduled to run at 12 AM - 2 AM local time for each teacher.

ENHANCEMENTS:
- Time window: 12 AM - 2 AM (not exact midnight)
- Sessions: TODAY (not tomorrow)
- Duplicate prevention: Check day+month+year
- UPSERT only for same day, else create new
- Multi-pillar RAG retrieval
- Rich context: education system, level, country
"""

import os
import sys
import logging
import traceback
import asyncio
import json
import re
import aiohttp
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytz
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import settings
from brief_sche.country_timezone_map import get_timezone_for_country, get_timezone_object

from .slide_schema import validate_slide_json, SlideDecks
from .slide_prompts import build_slide_generation_prompt, extract_image_prompts_from_slides
from .slide_retrieval import retrieve_all_pillars_for_slides, format_chunks_for_ai_prompt

# Configure logging
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "slide_log.txt")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

detail_logger = logging.getLogger("slide_detail")
detail_logger.setLevel(logging.INFO)
detail_logger.addHandler(file_handler)
detail_logger.addHandler(logging.StreamHandler(sys.stdout))  # Add console output
detail_logger.propagate = False


def is_in_generation_window(country: str, window_start: int = 0, window_end: int = 2) -> bool:
    """
    Check if the current local time for a country is in the generation window.
    
    Default window: 12 AM - 2 AM (hours 0, 1)
    
    Args:
        country: Country name from teacher profile
        window_start: Start hour (default 0 = midnight/12 AM)
        window_end: End hour (default 2 = 2 AM, exclusive)
        
    Returns:
        True if current local hour is within the window
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
    
    # Check if within window [window_start, window_end)
    in_window = window_start <= current_hour < window_end
    
    detail_logger.info(f"🕐 Country: {country} | Local time: {local_time.strftime('%H:%M')} | Hour: {current_hour} | Window: {window_start}-{window_end} | In window: {in_window}")
    
    return in_window


def get_local_date_for_country(country: str) -> date:
    """Get the current local date for a country."""
    tz = get_timezone_object(country)
    if tz:
        return datetime.now(tz).date()
    return datetime.utcnow().date()


async def get_teachers_for_processing() -> List[Dict[str, Any]]:
    """
    Get all teachers from the database with their country.
    
    Returns:
        List of teacher records with id, display_name, and country
    """
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
            rows = result.fetchall()
            return [
                {
                    "id": row._mapping["id"],
                    "display_name": row._mapping.get("display_name"),
                    "country": row._mapping["country"]
                }
                for row in rows
            ]
        finally:
            await db_gen.aclose()
    
    return await _fetch()


async def has_slides_for_today(teacher_id: UUID, local_date: date) -> bool:
    """
    Check if slides have already been generated for this teacher today.
    
    Compares the day+month+year of created_at with today's date.
    This prevents duplicate generation within the same day.
    
    Args:
        teacher_id: Teacher's UUID
        local_date: The local date to check against
        
    Returns:
        True if slides exist for today, False otherwise
    """
    async def _check():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            result = await db.execute(
                text("""
                    SELECT COUNT(*) as cnt
                    FROM slides
                    WHERE teacher_id = :teacher_id
                      AND DATE(created_at) = :check_date
                """),
                {
                    "teacher_id": str(teacher_id),
                    "check_date": local_date
                }
            )
            row = result.fetchone()
            count = row._mapping["cnt"] if row else 0
            return count > 0
        finally:
            await db_gen.aclose()
    
    return await _check()


async def get_sessions_for_today(
    teacher_id: UUID,
    country: str
) -> List[Dict[str, Any]]:
    """
    Get all class sessions scheduled for TODAY (local time).
    
    Returns:
        List of session data with subject, class_name, and session info
    """
    local_date = get_local_date_for_country(country)
    
    async def _fetch():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            result = await db.execute(
                text("""
                    SELECT DISTINCT 
                        cs.id,
                        cs.subject,
                        cs.class_name,
                        cs.date,
                        cs.start_time,
                        cs.end_time,
                        cs.session_number
                    FROM classsession cs
                    WHERE cs.teacher_id = :teacher_id
                      AND cs.date = :target_date
                      AND cs.is_completed = false
                    ORDER BY cs.start_time
                """),
                {"teacher_id": str(teacher_id), "target_date": local_date}
            )
            rows = result.fetchall()
            return [
                {
                    "id": row._mapping["id"],
                    "subject": row._mapping["subject"],
                    "class_name": row._mapping["class_name"],
                    "date": row._mapping["date"],
                    "start_time": row._mapping["start_time"],
                    "end_time": row._mapping["end_time"],
                    "session_number": row._mapping.get("session_number")
                }
                for row in rows
            ]
        finally:
            await db_gen.aclose()
    
    return await _fetch()


async def get_education_context(
    teacher_id: UUID,
    subject: str,
    class_name: str
) -> Dict[str, Any]:
    """
    Get education system and level from WeeklyTimeTable.
    Also get country from TeacherProfile.
    
    Returns:
        Dictionary with edu_sys, edu_lvl, and country
    """
    async def _fetch():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            edu_sys = None
            edu_lvl = None
            
            # Try to get education system/level from timetable
            # Note: These columns might not exist in all deployments
            try:
                tt_result = await db.execute(
                    text("""
                        SELECT education_system, education_level
                        FROM weeklytimetable
                        WHERE teacher_id = CAST(:teacher_id AS uuid)
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
                tt_row = tt_result.fetchone()
                if tt_row:
                    edu_sys = tt_row._mapping.get("education_system")
                    edu_lvl = tt_row._mapping.get("education_level")
            except Exception as e:
                # Columns might not exist - that's okay
                detail_logger.debug(f"Could not get education context from timetable: {e}")
            
            # Get country from teacher profile
            tp_result = await db.execute(
                text("""
                    SELECT country
                    FROM teacherprofile
                    WHERE id = CAST(:teacher_id AS uuid)
                """),
                {"teacher_id": str(teacher_id)}
            )
            tp_row = tp_result.fetchone()
            
            return {
                "edu_sys": edu_sys or "standard",
                "edu_lvl": edu_lvl or "secondary",
                "country": tp_row._mapping.get("country") if tp_row else None
            }
        except Exception as e:
            detail_logger.warning(f"Error getting education context: {e}")
            return {"edu_sys": "standard", "edu_lvl": "secondary", "country": None}
        finally:
            await db_gen.aclose()
    
    return await _fetch()


async def get_curriculum_for_session(
    session_id: int,
    teacher_id: UUID,
    subject: str,
    class_name: str
) -> Dict[str, Any]:
    """
    Get curriculum data (strand, substrand, content standard, indicator) for a session.
    
    Uses session_details JSONB field which contains:
    [{"id": 1822, "date": "2025-12-03", "end_time": "13:00", "start_time": "12:00", "week_number": 1}]
    """
    async def _fetch():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            # Find indicators where session_details contains this session ID
            # Using JSONB path query to search in the array
            result = await db.execute(
                text("""
                    SELECT 
                        i.id as indicator_id,
                        i.indicator_code,
                        i.indicator_text,
                        i.session_details,
                        cs.content_standard,
                        cs.content_standard_code,
                        ss.substrand_name,
                        s.strand_name
                    FROM indicator i
                    LEFT JOIN contentstandard cs ON i.content_standard_id = cs.id
                    LEFT JOIN substrand ss ON cs.substrand_id = ss.id
                    LEFT JOIN strand s ON ss.strand_id = s.id
                    WHERE i.teacher_id = :teacher_id
                      AND i.subject = :subject
                      AND i.class_name = :class_name
                      AND i.session_details IS NOT NULL
                      AND i.session_details @> :session_json
                    LIMIT 1
                """),
                {
                    "teacher_id": str(teacher_id),
                    "subject": subject,
                    "class_name": class_name,
                    "session_json": json.dumps([{"id": session_id}])
                }
            )
            row = result.fetchone()
            
            if row:
                mapping = row._mapping
                detail_logger.info(f"📚 Found curriculum for session {session_id}")
                detail_logger.info(f"   Strand: {mapping.get('strand_name')}")
                detail_logger.info(f"   Substrand: {mapping.get('substrand_name')}")
                detail_logger.info(f"   Indicator: {mapping.get('indicator_text', '')[:100]}...")
                return {
                    "indicator_id": mapping.get("indicator_id"),
                    "indicator_code": mapping.get("indicator_code"),
                    "indicator_text": mapping.get("indicator_text"),
                    "content_standard": mapping.get("content_standard"),
                    "content_standard_code": mapping.get("content_standard_code"),
                    "substrand_name": mapping.get("substrand_name"),
                    "strand_name": mapping.get("strand_name")
                }
            
            detail_logger.warning(f"⚠️ No curriculum found for session {session_id}")
            return {}
        finally:
            await db_gen.aclose()
    
    return await _fetch()


def build_enhanced_slide_prompt(
    subject: str,
    class_level: str,
    topic: str,
    curriculum: Dict[str, Any],
    education_context: Dict[str, Any],
    rag_content: str
) -> str:
    """
    Build an enhanced prompt with all context for slide generation.
    """
    edu_sys = education_context.get("edu_sys") or "standard"
    edu_lvl = education_context.get("edu_lvl") or "secondary"
    country = education_context.get("country") or "Ghana"
    
    indicator_text = curriculum.get("indicator_text") or ""
    content_standard = curriculum.get("content_standard") or ""
    strand_name = curriculum.get("strand_name") or ""
    substrand_name = curriculum.get("substrand_name") or ""
    
    from .slide_schema import get_schema_for_prompt, get_allowed_layouts, get_recommended_slide_count
    
    layouts = get_allowed_layouts()
    layouts_str = "\n  ".join(layouts)
    schema = get_schema_for_prompt()
    
    # Get recommended slide count based on education level
    slide_counts = get_recommended_slide_count(edu_lvl, class_level)
    min_slides = slide_counts["min_slides"]
    max_slides = slide_counts["max_slides"]
    
    prompt = f"""You are an expert educational content creator with mastery in multiple domains:

1. **COGNITIVE SCIENCE & LEARNING PSYCHOLOGY**: You understand how students learn, memory formation, attention spans, and cognitive load theory. Apply these principles to make slides that are cognitively optimized for learning.

2. **SUBJECT MATTER EXPERTISE in {subject.upper()}**: You are a master teacher of {subject} at the {edu_lvl} level in the {edu_sys} education system. You understand the depth and breadth of content appropriate for {class_level} students in {country}.

3. **LESSON DESIGN**: You are an expert in instructional design, knowing how to structure content for maximum engagement and retention. You know how to introduce concepts, build on prior knowledge, and scaffold learning.

4. **ASSESSMENT & EVALUATION**: You know how to check for understanding through well-crafted questions and formative assessments.

Generate lesson slides as JSON ONLY.
Do not include any explanations, markdown, or text outside the JSON.

CRITICAL: TYPE vs LAYOUT ARE DIFFERENT FIELDS!
==============================================
"type" = What kind of slide it is. ONLY these values allowed:
  - "title" (for title slides)
  - "content" (for regular text content)
  - "image_content" (for slides WITH images)
  - "assessment_mcq" (for MCQ assessment)
  - "assessment_essay" (for essay assessment)

"layout" = How the slide looks visually. ONLY these values allowed:
  - "title_center" (title in center)
  - "text_only" (just text)
  - "image_left_text_right" (image on left, text on right)
  - "image_top_text_bottom" (image on top, text below)
  - "assessment" (for assessment slides)

CORRECT EXAMPLE:
{{"id": "slide-3", "type": "image_content", "layout": "image_left_text_right", "content": {{...}}}}

WRONG EXAMPLE (DO NOT DO THIS):
{{"id": "slide-3", "type": "image_left_text_right", ...}} <-- WRONG! layout value in type field

STRICT RULES:
1. "type" MUST be one of: title, content, image_content, assessment_mcq, assessment_essay
2. "layout" MUST be one of: title_center, text_only, image_left_text_right, image_top_text_bottom, assessment
3. Limit bullet points to 5 per slide maximum
4. Use images only when they genuinely improve understanding
5. Prefer diagrams for science and math topics
6. Language must be appropriate for {edu_lvl} level students in {country}
7. Generate {min_slides}-{max_slides} slides total
8. Start with a title slide using type="title", layout="title_center"
9. **LAST 2 SLIDES MUST BE ASSESSMENT SLIDES:**
   - Second-to-last slide: type="assessment_mcq", layout="assessment" - 15 MCQs
   - Last slide: type="assessment_essay", layout="assessment" - 5 Essay Questions
10. Do NOT use markdown in any text content
11. Do NOT include extra keys not in the schema

ASSESSMENT REQUIREMENTS:
MCQ Slide (assessment_mcq):
- 15 questions in "mcq_questions" array
- Each: question, options (A/B/C/D), correct_answer, explanation

Essay Slide (assessment_essay):
- 5 questions in "essay_questions" array
- Each: question, key_points (2-3 points), marks (5-15)

EDUCATIONAL CONTEXT:
- Subject: {subject}
- Class Level: {class_level}
- Topic: {topic}
- Education System: {edu_sys}
- Education Level: {edu_lvl}
- Country: {country}

CURRICULUM CONTEXT:
- Strand: {strand_name}
- Substrand: {substrand_name}
- Content Standard: {content_standard}
- Learning Indicator: {indicator_text}

{rag_content}

REQUIRED JSON SCHEMA:
{schema}

IMAGE PROMPT GUIDELINES:
When including images, write clear, educational prompts:
- For diagrams: "flat educational diagram showing [concept], clean lines, labeled parts"
- For illustrations: "educational illustration of [concept], colorful, student-friendly"
- For photos: "real photograph of [subject], clear, high quality, educational context"

Generate the slides now. Return ONLY the valid JSON object.
"""
    
    return prompt


async def call_ai_for_slides(prompt: str) -> Dict[str, Any]:
    """
    Call Vertex AI to generate slides.
    """
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    import json as json_lib
    
    detail_logger.info("🤖 Calling Vertex AI for slide generation...")
    detail_logger.info("\n" + "=" * 80)
    detail_logger.info("PROMPT SENT TO AI")
    detail_logger.info("=" * 80)
    detail_logger.info(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
    detail_logger.info("=" * 80 + "\n")
    
    # Authentication
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
        
    except Exception as e:
        detail_logger.error(f"❌ Authentication failed: {e}")
        raise
    
    # Prepare request
    project_id = settings.GCS_PROJECT_ID
    # Using gemini-2.5-flash with increased output tokens
    model_id = "gemini-2.5-flash"
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generation_config": {
            "temperature": 0.3,
            "maxOutputTokens": 32768,
            "responseMimeType": "application/json"
        }
    }
    
    # Log full payload
    detail_logger.info("API Request Payload:")
    detail_logger.info(json.dumps(payload, indent=2)[:1000] + "...")
    
    # Send request with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=180)  # Longer timeout for larger output
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        response_data = json_lib.loads(response_text)
                        
                        # Extract content
                        if "candidates" in response_data and len(response_data["candidates"]) > 0:
                            content = response_data["candidates"][0].get("content", {})
                            if "parts" in content and len(content["parts"]) > 0:
                                result_text = content["parts"][0].get("text", "")
                                
                                detail_logger.info("AI Response received:")
                                detail_logger.info(result_text[:1000] + "..." if len(result_text) > 1000 else result_text)
                                
                                # Parse and validate JSON
                                try:
                                    slides_data = json_lib.loads(result_text)
                                except json_lib.JSONDecodeError:
                                    json_match = re.search(r'\{[\s\S]*\}', result_text)
                                    if json_match:
                                        slides_data = json_lib.loads(json_match.group(0))
                                    else:
                                        raise ValueError("No valid JSON found in AI response")
                                
                                # Validate against schema
                                validated_data = validate_slide_json(slides_data)
                                detail_logger.info(f"✅ Slide generation successful: {len(validated_data.get('slides', []))} slides")
                                return validated_data
                        
                        raise ValueError("No content in AI response")
                    
                    elif response.status == 429:
                        detail_logger.warning(f"⚠️ Rate limited (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(10 * (attempt + 1))
                        continue
                    else:
                        detail_logger.error(f"❌ API error: {response.status} - {response_text[:500]}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(5)
                            continue
                        raise ValueError(f"API error: {response.status}")
                        
        except asyncio.TimeoutError:
            detail_logger.warning(f"⏱️ Timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
                continue
            raise
        except Exception as e:
            detail_logger.error(f"❌ Error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)
                continue
            raise
    
    raise ValueError("Failed after all retries")


async def save_slide_deck(
    teacher_id: UUID,
    subject: str,
    class_name: str,
    topic: str,
    content_json: Dict[str, Any],
    indicator_ids: List[int],
    local_date: date
) -> Optional[str]:
    """
    Save slide deck to database.
    
    - If slides exist for same day+month+year, UPDATE them
    - Otherwise, CREATE new entry (preserving history)
    
    Returns:
        slide_id on success, None on failure
    """
    async def _save():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            detail_logger.info(f"   Checking for existing slides...")
            detail_logger.info(f"   teacher_id={teacher_id}, subject={subject}, class_name={class_name}")
            detail_logger.info(f"   local_date={local_date}")
            
            # Check if slides exist for today with same subject/class/topic
            existing_check = await db.execute(
                text("""
                    SELECT id FROM slides
                    WHERE teacher_id = CAST(:teacher_id AS uuid)
                      AND subject = :subject
                      AND class_name = :class_name
                      AND topic = :topic
                      AND DATE(created_at) = :check_date
                """),
                {
                    "teacher_id": str(teacher_id),
                    "subject": subject,
                    "class_name": class_name,
                    "topic": topic,
                    "check_date": local_date
                }
            )
            existing_row = existing_check.fetchone()
            
            if existing_row:
                # UPDATE existing slide for today
                existing_id = existing_row._mapping["id"]
                detail_logger.info(f"📝 Updating existing slide for today: {existing_id}")
                
                # Delete old images associated with this slide (cleanup before new ones)
                await db.execute(
                    text("DELETE FROM slide_images WHERE slide_id = CAST(:slide_id AS uuid)"),
                    {"slide_id": str(existing_id)}
                )
                detail_logger.info(f"🗑️ Cleaned up old images for slide: {existing_id}")
                
                await db.execute(
                    text("""
                        UPDATE slides SET
                            content_json = CAST(:content_json AS jsonb),
                            indicator_ids = CAST(:indicator_ids AS jsonb),
                            generation_status = 'completed',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = CAST(:slide_id AS uuid)
                    """),
                    {
                        "slide_id": str(existing_id),
                        "content_json": json.dumps(content_json),
                        "indicator_ids": json.dumps(indicator_ids)
                    }
                )
                await db.commit()
                detail_logger.info(f"✅ Updated slide: {existing_id}")
                return str(existing_id)
            else:
                # CREATE new slide (preserves history)
                detail_logger.info(f"➕ Creating new slide deck (preserving history)")
                
                result = await db.execute(
                    text("""
                        INSERT INTO slides (
                            id, teacher_id, subject, class_name, topic, 
                            content_json, indicator_ids, generation_status,
                            created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), CAST(:teacher_id AS uuid), :subject, :class_name, :topic,
                            CAST(:content_json AS jsonb), CAST(:indicator_ids AS jsonb), 'completed',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        RETURNING id
                    """),
                    {
                        "teacher_id": str(teacher_id),
                        "subject": subject,
                        "class_name": class_name,
                        "topic": topic,
                        "content_json": json.dumps(content_json),
                        "indicator_ids": json.dumps(indicator_ids)
                    }
                )
                await db.commit()
                row = result.fetchone()
                if row:
                    slide_id = str(row._mapping["id"])
                    detail_logger.info(f"✅ Created new slide: {slide_id}")
                    return slide_id
                else:
                    detail_logger.error("❌ INSERT returned no row")
                    return None
                
        except Exception as e:
            detail_logger.error(f"❌ Failed to save slide deck: {e}")
            import traceback
            detail_logger.error(traceback.format_exc())
            await db.rollback()
            return None
        finally:
            await db_gen.aclose()
    
    return await _save()


async def save_image_prompts(
    slide_id: str,
    image_prompts: List[Dict[str, Any]]
) -> int:
    """Save image prompts for later generation."""
    if not image_prompts:
        return 0
    
    async def _save():
        db_gen = get_db()
        db = await anext(db_gen)
        try:
            saved_count = 0
            for img in image_prompts:
                await db.execute(
                    text("""
                        INSERT INTO slide_images (
                            id, slide_id, slide_item_id, prompt, style, alt_text, status,
                            created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), CAST(:slide_id AS uuid), :slide_item_id, :prompt, :style, :alt_text, 'pending',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "slide_id": slide_id,
                        "slide_item_id": img.get("slide_item_id", ""),
                        "prompt": img.get("enhanced_prompt", img.get("prompt", "")),
                        "style": str(img.get("style", "")),
                        "alt_text": img.get("alt", "")
                    }
                )
                saved_count += 1
            await db.commit()
            return saved_count
        except Exception as e:
            detail_logger.error(f"❌ Failed to save image prompts: {e}")
            await db.rollback()
            return 0
        finally:
            await db_gen.aclose()
    
    return await _save()


async def process_session_slides(
    teacher_id: UUID,
    session: Dict[str, Any],
    country: str,
    local_date: date
) -> bool:
    """
    Generate slides for a single session.
    """
    session_id = session["id"]
    subject = session["subject"]
    class_name = session["class_name"]
    
    detail_logger.info(f"\n📚 Processing slides for: {subject} - {class_name}")
    detail_logger.info(f"   Session ID: {session_id}")
    detail_logger.info(f"   Session Date: {session.get('date')}")
    
    try:
        # Get curriculum context
        curriculum = await get_curriculum_for_session(
            session_id, teacher_id, subject, class_name
        )
        
        # Skip if no curriculum data found
        if not curriculum or not curriculum.get("indicator_text"):
            detail_logger.warning(f"⏭️ Skipping session {session_id} - no curriculum data found")
            return False
        
        # Get education context (edu_sys, edu_lvl, country)
        education_context = await get_education_context(teacher_id, subject, class_name)
        if not education_context.get("country"):
            education_context["country"] = country
        
        detail_logger.info(f"   Education System: {education_context.get('edu_sys')}")
        detail_logger.info(f"   Education Level: {education_context.get('edu_lvl')}")
        detail_logger.info(f"   Country: {education_context.get('country')}")
        
        # Build topic from indicator or use subject
        topic = curriculum.get("indicator_text") or f"{subject} Lesson"
        if len(topic) > 100:
            topic = topic[:97] + "..."
        
        # Retrieve knowledge from all pillars
        detail_logger.info(f"\n🔍 Starting RAG retrieval for slide generation...")
        rag_chunks = await retrieve_all_pillars_for_slides(
            subject=subject,
            class_name=class_name,
            topic=topic,
            indicator_text=curriculum.get("indicator_text"),
            content_standard=curriculum.get("content_standard"),
            strand_name=curriculum.get("strand_name"),
            teacher_id=teacher_id
        )
        
        # Format RAG chunks for prompt
        rag_content = format_chunks_for_ai_prompt(rag_chunks)
        detail_logger.info(f"📖 RAG content length: {len(rag_content)} characters")
        
        # Build enhanced prompt
        prompt = build_enhanced_slide_prompt(
            subject=subject,
            class_level=class_name,
            topic=topic,
            curriculum=curriculum,
            education_context=education_context,
            rag_content=rag_content
        )
        
        # Generate slides
        slides_data = await call_ai_for_slides(prompt)
        
        # Collect indicator IDs
        indicator_ids = []
        if curriculum.get("indicator_id"):
            indicator_ids.append(curriculum["indicator_id"])
        
        # Save slide deck
        slide_id = await save_slide_deck(
            teacher_id=teacher_id,
            subject=subject,
            class_name=class_name,
            topic=topic,
            content_json=slides_data,
            indicator_ids=indicator_ids,
            local_date=local_date
        )
        
        if slide_id:
            detail_logger.info(f"✅ Saved slide deck: {slide_id}")
            
            # Extract and save image prompts for later processing
            image_prompts = extract_image_prompts_from_slides(slides_data)
            if image_prompts:
                saved = await save_image_prompts(slide_id, image_prompts)
                detail_logger.info(f"🖼️ Queued {saved} images for generation")
                
                # Generate images immediately
                from .image_generator import generate_images_for_slide
                generated = await generate_images_for_slide(slide_id)
                detail_logger.info(f"✅ Generated {generated} images")
            
            
            # Generate Student Lesson Pack (Background Task - Non-blocking)
            try:
                from .student_pack_generator import generate_student_pack
                detail_logger.info("🎒 Triggering Student Lesson Pack generation (background)...")
                
                # Run as background task - don't await
                asyncio.create_task(
                    generate_student_pack(
                        slide_id=slide_id,
                        session_id=str(session["id"]),
                        teacher_id=str(teacher_id),
                        subject=subject,
                        class_name=class_name
                    )
                )
                detail_logger.info("✅ Student Lesson Pack generation started in background")
            except ImportError as e:
                detail_logger.warning(f"⚠️ Student pack generator not available: {e}")
            except Exception as e:
                detail_logger.error(f"❌ Error triggering student pack: {e}")
                import traceback
                detail_logger.error(traceback.format_exc())
            
            return True
        else:
            detail_logger.error(f"❌ Failed to save slide deck")
            return False
            
    except Exception as e:
        detail_logger.error(f"❌ Error processing slides: {e}")
        detail_logger.error(traceback.format_exc())
        return False


async def process_teacher_slides(
    teacher_id: UUID,
    country: str,
    display_name: Optional[str] = None
) -> int:
    """
    Process all slides for a single teacher.
    """
    detail_logger.info(f"\n{'='*60}")
    detail_logger.info(f"👨‍🏫 Processing slides for teacher: {display_name or teacher_id}")
    detail_logger.info(f"   Country: {country}")
    
    # Get local date for the teacher
    local_date = get_local_date_for_country(country)
    detail_logger.info(f"   Local date: {local_date}")
    
    # Check if slides already generated today
    if await has_slides_for_today(teacher_id, local_date):
        detail_logger.info(f"   ⏭️ Slides already generated today - skipping")
        return 0
    
    # Get sessions for TODAY
    sessions = await get_sessions_for_today(teacher_id, country)
    
    if not sessions:
        detail_logger.info(f"   No sessions scheduled for today")
        return 0
    
    detail_logger.info(f"   Found {len(sessions)} sessions for today")
    
    success_count = 0
    for session in sessions:
        try:
            if await process_session_slides(teacher_id, session, country, local_date):
                success_count += 1
        except Exception as e:
            detail_logger.error(f"❌ Failed to process session {session['id']}: {e}")
            continue
    
    detail_logger.info(f"   Generated {success_count}/{len(sessions)} slide decks")
    return success_count


async def run_slide_generation_cycle():
    """
    Main entry point called by the scheduler.
    
    Loops through all teachers and generates slides for those 
    whose local time is in the 12 AM - 2 AM window.
    """
    detail_logger.info("\n" + "=" * 80)
    detail_logger.info(f"🎬 SLIDE GENERATION CYCLE STARTED - {datetime.utcnow().isoformat()}")
    detail_logger.info("=" * 80)
    
    try:
        # Get all teachers
        teachers = await get_teachers_for_processing()
        detail_logger.info(f"📋 Found {len(teachers)} teachers with country set")
        
        processed_count = 0
        total_slides = 0
        
        for teacher in teachers:
            teacher_id = teacher["id"]
            country = teacher["country"]
            display_name = teacher.get("display_name")
            
            # Check if teacher is in the 12 AM - 2 AM window
            if not is_in_generation_window(country, window_start=0, window_end=2):
                continue
            
            detail_logger.info(f"\n🌙 {display_name or teacher_id} is in midnight window - generating slides")
            
            try:
                slides_generated = await process_teacher_slides(
                    teacher_id=teacher_id,
                    country=country,
                    display_name=display_name
                )
                processed_count += 1
                total_slides += slides_generated
            except Exception as e:
                detail_logger.error(f"❌ Error processing teacher {teacher_id}: {e}")
                detail_logger.error(traceback.format_exc())
                continue
        
        detail_logger.info(f"\n{'='*80}")
        detail_logger.info(f"✅ SLIDE GENERATION CYCLE COMPLETED")
        detail_logger.info(f"   Teachers processed: {processed_count}")
        detail_logger.info(f"   Total slides generated: {total_slides}")
        detail_logger.info("=" * 80 + "\n")
        
    except Exception as e:
        detail_logger.error(f"❌ SLIDE GENERATION CYCLE FAILED: {e}")
        detail_logger.error(traceback.format_exc())


async def enqueue_slide_generation_cycle():
    """
    Scheduler entry point that ENQUEUES tasks instead of processing directly.
    
    This keeps the API server responsive by offloading slide generation
    to background workers via Redis queue.
    """
    detail_logger.info("\n" + "=" * 80)
    detail_logger.info(f"🎬 ENQUEUEING SLIDE GENERATION - {datetime.utcnow().isoformat()}")
    detail_logger.info("=" * 80)
    
    try:
        from .enqueue_slide import enqueue_slide_generation
        
        # Get all teachers
        teachers = await get_teachers_for_processing()
        detail_logger.info(f"📋 Found {len(teachers)} teachers with country set")
        
        enqueued_count = 0
        
        for teacher in teachers:
            teacher_id = teacher["id"]
            country = teacher["country"]
            display_name = teacher.get("display_name")
            
            # Check if teacher is in the 12 AM - 2 AM window
            if not is_in_generation_window(country, window_start=0, window_end=2):
                continue
            
            detail_logger.info(f"🌙 {display_name or teacher_id} is in midnight window - enqueueing")
            
            try:
                # Enqueue task to Redis instead of direct processing
                job = await enqueue_slide_generation(
                    teacher_id=str(teacher_id),
                    subject="",  # Will be determined from timetable
                    class_name="",  # Will be determined from timetable
                    country=country,
                    delay=enqueued_count * 5  # Stagger by 5 seconds each
                )
                detail_logger.info(f"   ✅ Enqueued: Job {job.job_id}")
                enqueued_count += 1
            except Exception as e:
                detail_logger.error(f"   ❌ Failed to enqueue: {e}")
                continue
        
        detail_logger.info(f"\n{'='*80}")
        detail_logger.info(f"✅ SLIDE GENERATION ENQUEUE COMPLETED")
        detail_logger.info(f"   Tasks enqueued: {enqueued_count}")
        detail_logger.info(f"   Workers will process in background")
        detail_logger.info("=" * 80 + "\n")
        
        return enqueued_count
        
    except Exception as e:
        detail_logger.error(f"❌ SLIDE GENERATION ENQUEUE FAILED: {e}")
        detail_logger.error(traceback.format_exc())
        return 0


# For testing
if __name__ == "__main__":
    asyncio.run(run_slide_generation_cycle())
