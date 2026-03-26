"""
Inline Outline Generation Utility

This module provides outline generation that runs INLINE within semester plan
background tasks, NOT as a separate background task.

This ensures atomic operation: if outline fails, the entire plan creation fails.
"""

import logging
import traceback
import json
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID

# Set up logging
logger = logging.getLogger(__name__)

# Create detailed file logger
import os
log_file = os.path.join(os.path.dirname(__file__), 'inline_outline.log')
detail_logger = logging.getLogger('inline_outline_detail')
detail_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
detail_logger.addHandler(file_handler)
detail_logger.propagate = False


async def generate_outline_inline(
    db,  # AsyncSession - reuse the existing session from plan processor
    teacher_id: str,
    subject: str,
    class_name: str,
    education_system: Optional[str] = None,
    academic_level: Optional[str] = None,
    semester_name: Optional[str] = None,
    term: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate course outline INLINE within the same transaction as plan creation.
    
    This function is meant to be called directly from plan processors (free, semplan, curri)
    AFTER the plan data has been stored but BEFORE the final success notification.
    
    If this function raises an exception, the entire plan creation should fail.
    
    Args:
        db: Async database session (reused from plan processor)
        teacher_id: Teacher UUID string
        subject: Subject name
        class_name: Class name
        education_system: Education system (e.g., 'ges', 'cambridge')
        academic_level: Academic level (e.g., 'k12', 'university')
        semester_name: Semester name
        term: Term name
        
    Returns:
        Dict with outline generation results
        
    Raises:
        Exception: If outline generation fails (will fail the entire plan)
    """
    logger.info(f"📘 [INLINE OUTLINE] Starting outline generation for {subject} - {class_name}")
    detail_logger.info("=" * 100)
    detail_logger.info(f"INLINE OUTLINE GENERATION - {datetime.now().isoformat()}")
    detail_logger.info("=" * 100)
    detail_logger.info(f"Teacher ID: {teacher_id}")
    detail_logger.info(f"Subject: {subject}")
    detail_logger.info(f"Class: {class_name}")
    detail_logger.info(f"Education System: {education_system}")
    detail_logger.info(f"Academic Level: {academic_level}")
    detail_logger.info(f"Semester: {semester_name}")
    detail_logger.info(f"Term: {term}")
    
    try:
        # Step 1: Fetch curriculum data from the just-stored plan
        detail_logger.info("Step 1: Fetching curriculum data...")
        
        # CRITICAL: Synchronize session to see flushed data
        # The plan was just stored with flush(), we need to ensure
        # the session sees the flushed (but uncommitted) data
        await db.flush()  # Ensure all pending writes are sent to DB
        
        # Check session state for debugging
        detail_logger.info(f"Session state - has pending changes: {db.new or db.dirty or db.deleted}")
        
        curriculum_data = await _fetch_curriculum_data(db, teacher_id, subject, class_name)
        
        if not curriculum_data or not curriculum_data.get('strands'):
            error_msg = f"No curriculum data found for {subject} - {class_name}"
            detail_logger.error(error_msg)
            raise Exception(error_msg)
        
        detail_logger.info(f"Found curriculum data:")
        detail_logger.info(f"  Strands: {len(curriculum_data.get('strands', []))}")
        detail_logger.info(f"  Substrands: {len(curriculum_data.get('substrands', []))}")
        detail_logger.info(f"  Content Standards: {len(curriculum_data.get('content_standards', []))}")
        detail_logger.info(f"  Indicators: {len(curriculum_data.get('indicators', []))}")
        
        # Step 2: Build AI prompt
        detail_logger.info("Step 2: Building AI prompt...")
        prompt = _build_outline_prompt(
            curriculum_data=curriculum_data,
            subject=subject,
            class_name=class_name,
            education_system=education_system,
            academic_level=academic_level,
            semester_name=semester_name,
            term=term
        )
        
        detail_logger.info(f"Prompt Length: {len(prompt)} characters")
        detail_logger.info("Full prompt logged below:")
        detail_logger.info(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        
        # Step 3: Call AI for outline generation
        detail_logger.info("Step 3: Calling AI model...")
        outline_content = await _call_ai_for_outline(prompt)
        
        detail_logger.info(f"AI response received - {len(outline_content)} characters")
        detail_logger.info("AI response (first 1000 chars):")
        detail_logger.info(outline_content[:1000] if outline_content else "EMPTY")
        
        # Step 4: Store outline in database (using same db session)
        detail_logger.info("Step 4: Storing outline in database...")
        await _store_outline_in_db(
            db=db,
            teacher_id=teacher_id,
            subject=subject,
            class_name=class_name,
            outline_content=outline_content,
            education_system=education_system,
            academic_level=academic_level,
            semester_name=semester_name,
            term=term
        )
        
        detail_logger.info("✅ Outline stored successfully")
        logger.info(f"✅ [INLINE OUTLINE] Outline generated for {subject} - {class_name}")
        
        return {
            "status": "success",
            "message": f"Outline generated for {subject} - {class_name}",
            "outline_length": len(outline_content)
        }
        
    except Exception as e:
        detail_logger.error(f"❌ INLINE OUTLINE GENERATION FAILED: {e}")
        detail_logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error(f"❌ [INLINE OUTLINE] Failed: {e}")
        # Re-raise to fail the entire plan creation
        raise Exception(f"Outline generation failed: {e}")


async def _fetch_curriculum_data(db, teacher_id: str, subject: str, class_name: str) -> Dict[str, Any]:
    """Fetch curriculum data from database using existing session.
    
    Uses SQLAlchemy ORM queries to properly handle UUID types and see flushed (uncommitted) data.
    """
    from sqlalchemy import select, and_, text
    from uuid import UUID as PyUUID
    from app.models.model import Strand, Substrand, ContentStandard, Indicator
    
    teacher_uuid = PyUUID(teacher_id) if isinstance(teacher_id, str) else teacher_id
    
    detail_logger.info(f"Fetching curriculum data for teacher_id={teacher_uuid}, subject={subject}, class_name={class_name}")
    
    # DEBUG: Check session's pending objects
    try:
        new_objects = list(db.new)
        detail_logger.info(f"DEBUG: Session has {len(new_objects)} NEW objects")
        for obj in new_objects[:5]:  # Log first 5
            detail_logger.info(f"  NEW: {type(obj).__name__} - {getattr(obj, 'id', 'no id')}")
    except Exception as e:
        detail_logger.info(f"DEBUG: Could not check session.new: {e}")
    
    # DEBUG: Try raw SQL to see if data exists
    try:
        raw_result = await db.execute(
            text("SELECT COUNT(*) FROM strand WHERE teacher_id = :tid AND subject = :subj AND class_name = :cls"),
            {"tid": str(teacher_uuid), "subj": subject, "cls": class_name}
        )
        count = raw_result.scalar()
        detail_logger.info(f"DEBUG: Raw SQL count of strands: {count}")
    except Exception as e:
        detail_logger.info(f"DEBUG: Raw SQL check failed: {e}")
    
    # Fetch strands using ORM
    strands_result = await db.execute(
        select(Strand).where(
            and_(
                Strand.teacher_id == teacher_uuid,
                Strand.subject == subject,
                Strand.class_name == class_name
            )
        )
    )
    strand_objects = strands_result.scalars().all()
    strands = [{
        "id": s.id,
        "strand_name": s.strand_name,
        "subject": s.subject,
        "class_name": s.class_name,
        "week_number": s.week_number,
        "session_ids": s.session_ids,
        "session_details": s.session_details
    } for s in strand_objects]
    
    detail_logger.info(f"Found {len(strands)} strands via ORM query")
    
    # Fetch substrands using ORM
    substrands_result = await db.execute(
        select(Substrand).where(
            and_(
                Substrand.teacher_id == teacher_uuid,
                Substrand.subject == subject,
                Substrand.class_name == class_name
            )
        )
    )
    substrand_objects = substrands_result.scalars().all()
    substrands = [{
        "id": ss.id,
        "substrand_name": ss.substrand_name,
        "strand_id": ss.strand_id,
        "subject": ss.subject,
        "class_name": ss.class_name,
        "week_numbers": ss.week_numbers,
        "session_ids": ss.session_ids,
        "session_details": ss.session_details
    } for ss in substrand_objects]
    
    detail_logger.info(f"Found {len(substrands)} substrands")
    
    # Fetch content standards using ORM
    content_standards_result = await db.execute(
        select(ContentStandard).where(
            and_(
                ContentStandard.teacher_id == teacher_uuid,
                ContentStandard.subject == subject,
                ContentStandard.class_name == class_name
            )
        )
    )
    cs_objects = content_standards_result.scalars().all()
    content_standards = [{
        "id": cs.id,
        "content_standard_code": cs.content_standard_code,
        "content_standard": cs.content_standard,
        "substrand_id": cs.substrand_id,
        "subject": cs.subject,
        "class_name": cs.class_name,
        "session_ids": cs.session_ids,
        "session_details": cs.session_details
    } for cs in cs_objects]
    
    detail_logger.info(f"Found {len(content_standards)} content standards")
    
    # Fetch indicators using ORM
    indicators_result = await db.execute(
        select(Indicator).where(
            and_(
                Indicator.teacher_id == teacher_uuid,
                Indicator.subject == subject,
                Indicator.class_name == class_name
            )
        )
    )
    ind_objects = indicators_result.scalars().all()
    indicators = [{
        "id": ind.id,
        "indicator_code": ind.indicator_code,
        "indicator_text": ind.indicator_text,
        "content_standard_id": ind.content_standard_id,
        "subject": ind.subject,
        "class_name": ind.class_name,
        "session_ids": ind.session_ids,
        "session_details": ind.session_details
    } for ind in ind_objects]
    
    detail_logger.info(f"Found {len(indicators)} indicators")
    
    return {
        "strands": strands,
        "substrands": substrands,
        "content_standards": content_standards,
        "indicators": indicators
    }


def _build_outline_prompt(
    curriculum_data: Dict[str, Any],
    subject: str,
    class_name: str,
    education_system: Optional[str],
    academic_level: Optional[str],
    semester_name: Optional[str],
    term: Optional[str]
) -> str:
    """Build AI prompt for course outline generation."""
    
    # Format curriculum data
    strands_text = ""
    for strand in curriculum_data.get("strands", []):
        strands_text += f"\n- {strand.get('strand_name', 'Unknown')} (Week {strand.get('week_number', 'N/A')})"
    
    substrands_text = ""
    for substrand in curriculum_data.get("substrands", []):
        substrands_text += f"\n- {substrand.get('substrand_name', 'Unknown')}"
    
    content_standards_text = ""
    for cs in curriculum_data.get("content_standards", []):
        cs_code = cs.get('content_standard_code', '')
        cs_content = cs.get('content_standard', '')
        content_standards_text += f"\n- [{cs_code}] {cs_content}"
    
    indicators_text = ""
    for ind in curriculum_data.get("indicators", []):
        ind_code = ind.get('indicator_code', '')
        ind_text = ind.get('indicator_text', '')
        indicators_text += f"\n- [{ind_code}] {ind_text}"
    
    prompt = f"""You are an expert educational curriculum designer. Generate a comprehensive course/subject outline based on the following curriculum data.

CONTEXT:
- Subject: {subject}
- Class: {class_name}
- Education System: {education_system or 'Not specified'}
- Academic Level: {academic_level or 'Not specified'}
- Semester: {semester_name or 'Not specified'}
- Term: {term or 'Not specified'}

CURRICULUM DATA:

STRANDS:{strands_text or ' None'}

SUBSTRANDS:{substrands_text or ' None'}

CONTENT STANDARDS:{content_standards_text or ' None'}

INDICATORS:{indicators_text or ' None'}

INSTRUCTIONS:
Generate a structured course outline in JSON format with the following structure:

{{
  "terminology": {{
    "type": "Course",
    "role": "Lecturer"
  }},
  "schoolInfoHeaders": [
    "School/University Name",
    "Department Name",
    "Program Name"
  ],
  "lectureInfo": {{
    "left": [
      {{"label": "Course Code", "value": ""}},
      {{"label": "Course Title", "value": "{subject}"}},
      {{"label": "Course Lecturer", "value": ""}},
      {{"label": "Email", "value": ""}}
    ],
    "right": [
      {{"label": "Credit Hour(s)", "value": ""}},
      {{"label": "Office Hours", "value": ""}},
      {{"label": "Room", "value": ""}},
      {{"label": "Phone", "value": ""}}
    ]
  }},
  "courseObjectives": [
    "Objective 1 based on curriculum content",
    "Objective 2 based on curriculum content",
    "Objective 3 based on curriculum content"
  ],
  "courseDescription": "A comprehensive description of the course based on the curriculum content provided. Include information about what students will learn and the overall scope of the course.",
  "learningOutcomes": [
    "By the end of this course, students will be able to...",
    "Students will demonstrate...",
    "Students will apply..."
  ],
  "courseDelivery": "Description of teaching methods including lectures, practical sessions, group work, projects, and assessments.",
  "courseContent": [
    {{"topic": "Week 1 topic based on curriculum", "activity": "Teaching activities for week 1"}},
    {{"topic": "Week 2 topic", "activity": "Teaching activities for week 2"}},
    {{"topic": "Week 3 topic", "activity": "Teaching activities for week 3"}}
  ],
  "policies": [
    "Attendance policy",
    "Academic integrity policy",
    "Late submission policy",
    "Assessment policy"
  ]
}}

IMPORTANT INSTRUCTIONS:
1. Return ONLY valid JSON. Do not wrap in markdown code blocks.
2. Generate 12-16 weeks of courseContent based on the curriculum structure provided.
3. Each week's topic should map to the strands/substrands/content standards from the curriculum.
4. Make courseObjectives, learningOutcomes, and courseDescription specific to the subject: {subject}
5. Use professional academic language appropriate for the education level.
"""
    
    return prompt


async def _call_ai_for_outline(prompt: str) -> str:
    """Call AI model to generate outline content with exponential backoff retry logic."""
    import aiohttp
    import asyncio
    import time
    import json as json_lib
    from app.core.config import settings
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    
    detail_logger.info("Authenticating with Vertex AI...")
    
    # Retry configuration
    max_retries = 5
    max_auth_retries = 5
    auth_retry_delay = 2
    access_token = None
    
    # Authenticate with Vertex AI - with exponential backoff
    for auth_attempt in range(max_auth_retries):
        try:
            detail_logger.info(f"🔄 Fetching access token (attempt {auth_attempt + 1}/{max_auth_retries})...")
            
            # Load service account credentials
            if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
                service_account_info = json_lib.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
            else:
                with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                    service_account_info = json_lib.load(f)
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Get access token
            credentials.refresh(Request())
            access_token = credentials.token
            
            detail_logger.info("✅ Successfully obtained access token")
            break
            
        except Exception as e:
            if auth_attempt < max_auth_retries - 1:
                detail_logger.warning(f"⚠️ Authentication error: {str(e)[:100]}. Retrying in {auth_retry_delay}s...")
                time.sleep(auth_retry_delay)
                auth_retry_delay *= 2  # Exponential backoff
            else:
                detail_logger.error(f"❌ Failed to authenticate after {max_auth_retries} attempts")
                raise Exception(f"Failed to authenticate with Vertex AI: {e}")
    
    if not access_token:
        raise Exception("Failed to obtain access token")
    
    # Use Vertex AI endpoint - matching the working outline_processor.py
    project_id = settings.GCS_PROJECT_ID
    model_id = "gemini-2.5-flash"
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
    
    detail_logger.info(f"🔗 Sending request to Vertex AI: {model_id}")
    
    # Create payload
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generation_config": {
            "temperature": 0.5,
            "maxOutputTokens": 65536
        }
    }
    
    # Set headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Retry loop for API calls with exponential backoff
    attempt = 0
    retry_delay = 20  # Initial retry delay
    
    while attempt < max_retries:
        try:
            if attempt > 0:
                detail_logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries} after {retry_delay}s wait...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                detail_logger.info(f"📤 Sending request (attempt {attempt + 1}/{max_retries})...")
            
            # Send request
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response_text = await response.text()
                    
                    detail_logger.info(f"📡 Response Status: {response.status}")
                    
                    # Success
                    if response.status == 200:
                        response_data = json_lib.loads(response_text)
                        detail_logger.info(f"✅ Response received successfully")
                        
                        # Extract content
                        if "candidates" in response_data and len(response_data["candidates"]) > 0:
                            content = response_data["candidates"][0].get("content", {})
                            if "parts" in content and len(content["parts"]) > 0:
                                result_text = content["parts"][0].get("text", "")
                                detail_logger.info(f"✅ Received {len(result_text)} characters from AI")
                                
                                # Clean markdown code blocks from AI response
                                cleaned_text = result_text.strip()
                                
                                # Remove ```json at start
                                if cleaned_text.startswith("```json"):
                                    cleaned_text = cleaned_text[7:]
                                elif cleaned_text.startswith("```"):
                                    cleaned_text = cleaned_text[3:]
                                
                                # Remove ``` at end
                                if cleaned_text.endswith("```"):
                                    cleaned_text = cleaned_text[:-3]
                                
                                cleaned_text = cleaned_text.strip()
                                
                                # Validate it's valid JSON
                                try:
                                    json_lib.loads(cleaned_text)
                                    detail_logger.info(f"✅ Validated JSON - {len(cleaned_text)} characters")
                                except json_lib.JSONDecodeError as e:
                                    detail_logger.warning(f"⚠️ AI response is not valid JSON: {e}")
                                    detail_logger.warning(f"First 500 chars: {cleaned_text[:500]}")
                                
                                return cleaned_text
                            else:
                                detail_logger.warning("No content parts found in response")
                                return ""
                        else:
                            detail_logger.warning("No candidates found in response")
                            return ""
                    
                    # Handle 429 rate limit - exponential backoff
                    elif response.status == 429:
                        attempt += 1
                        
                        if attempt < max_retries:
                            quota_wait_time = 10 * (2 ** attempt)  # Exponential: 20s, 40s, 80s, 160s...
                            detail_logger.warning(f"⚠️ Quota/rate limit hit (429). Retrying in {quota_wait_time}s... (Attempt {attempt}/{max_retries})")
                            await asyncio.sleep(quota_wait_time)
                            continue
                        else:
                            detail_logger.error(f"❌ Max retry attempts reached for rate limit errors")
                            raise Exception(f"AI outline generation failed after {max_retries} attempts due to quota exhaustion")
                    
                    # Other errors
                    else:
                        detail_logger.error(f"❌ API request failed with status {response.status}: {response_text[:200]}")
                        attempt += 1
                        if attempt < max_retries:
                            detail_logger.info(f"   Retrying in {retry_delay}s...")
                            continue
                        raise Exception(f"AI API request failed with status {response.status}")
        
        except asyncio.TimeoutError:
            attempt += 1
            if attempt < max_retries:
                detail_logger.warning(f"⏱️ Request timed out. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise Exception("AI request timed out after multiple attempts")
                
        except Exception as e:
            if "rate limit" in str(e).lower() or "quota" in str(e).lower() or "429" in str(e):
                attempt += 1
                if attempt < max_retries:
                    wait_time = 10 * (2 ** attempt)
                    detail_logger.warning(f"💥 Rate limit error: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
            detail_logger.error(f"💥 Error during AI call: {e}")
            attempt += 1
            if attempt < max_retries:
                detail_logger.info(f"   Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise
                
    raise Exception("Failed to generate outline after max retries")


async def _store_outline_in_db(
    db,
    teacher_id: str,
    subject: str,
    class_name: str,
    outline_content: str,
    education_system: Optional[str],
    academic_level: Optional[str],
    semester_name: Optional[str],
    term: Optional[str]
):
    """Store generated outline in database using existing session."""
    from sqlalchemy import text
    from datetime import datetime
    
    # Check if outline exists for this teacher/subject/class combination
    existing = await db.execute(
        text("""
            SELECT id FROM outline 
            WHERE teacher_id = :teacher_id 
              AND subject = :subject 
              AND class_name = :class_name
        """),
        {"teacher_id": teacher_id, "subject": subject, "class_name": class_name}
    )
    existing_row = existing.fetchone()
    
    if existing_row:
        # Update existing outline
        await db.execute(
            text("""
                UPDATE outline 
                SET outline_content = :outline_content,
                    education_system = :education_system,
                    academic_level = :academic_level,
                    semester_name = :semester_name,
                    term = :term,
                    updated_at = :updated_at,
                    is_active = TRUE
                WHERE teacher_id = :teacher_id 
                  AND subject = :subject 
                  AND class_name = :class_name
            """),
            {
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name,
                "outline_content": outline_content,
                "education_system": education_system,
                "academic_level": academic_level,
                "semester_name": semester_name,
                "term": term,
                "updated_at": datetime.utcnow()
            }
        )
        detail_logger.info(f"Updated existing outline for {subject} - {class_name}")
    else:
        # Insert new outline
        await db.execute(
            text("""
                INSERT INTO outline 
                (teacher_id, subject, class_name, outline_content, education_system, academic_level, semester_name, term, created_at, updated_at, is_active)
                VALUES (:teacher_id, :subject, :class_name, :outline_content, :education_system, :academic_level, :semester_name, :term, :created_at, :updated_at, TRUE)
            """),
            {
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name,
                "outline_content": outline_content,
                "education_system": education_system,
                "academic_level": academic_level,
                "semester_name": semester_name,
                "term": term,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )
        detail_logger.info(f"Created new outline for {subject} - {class_name}")
    
    # Note: Don't commit here - let the caller handle the commit
    # This ensures atomicity with the plan creation

