"""
Course/Subject Outline Background Processor

Generates comprehensive course/subject outlines from curriculum data.
Used by Teacher Lesson Pack feature.
"""

import os
import sys
import json
import logging
import traceback
import asyncio
from datetime import datetime
from uuid import UUID
from typing import Dict, List, Optional, Any

# Configure base logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create dedicated file logger
outline_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.txt")
file_handler = logging.FileHandler(outline_log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Create a separate logger for detailed logging
detail_logger = logging.getLogger("outline_detail")
detail_logger.setLevel(logging.INFO)
detail_logger.addHandler(file_handler)
detail_logger.propagate = False

def log_separator():
    """Log a separator line for readability"""
    detail_logger.info("=" * 100)

def log_section(title: str):
    """Log a section header"""
    detail_logger.info("")
    detail_logger.info("=" * 100)
    detail_logger.info(f"  {title}")
    detail_logger.info("=" * 100)


async def process_outline_task(
    task_id: str,
    teacher_id: str,
    subject: str,
    class_name: str,
    education_system: Optional[str] = None,
    academic_level: Optional[str] = None,
    semester_name: Optional[str] = None,
    term: Optional[str] = None
):
    """
    Process outline generation task.
    
    Args:
        task_id: Unique task ID
        teacher_id: Teacher UUID
        subject: Subject name
        class_name: Class name
        education_system: Education system (e.g., 'ges', 'cambridge')
        academic_level: Academic level (e.g., 'k12', 'university')
        semester_name: Semester name
        term: Term name
    """
    try:
        log_section(f"OUTLINE GENERATION STARTED - {datetime.now().isoformat()}")
        detail_logger.info(f"Task ID: {task_id}")
        detail_logger.info(f"Teacher ID: {teacher_id}")
        detail_logger.info(f"Subject: {subject}")
        detail_logger.info(f"Class: {class_name}")
        detail_logger.info(f"Education System: {education_system}")
        detail_logger.info(f"Academic Level: {academic_level}")
        detail_logger.info(f"Semester: {semester_name}")
        detail_logger.info(f"Term: {term}")
        
        logger.info(f"Starting outline generation for {subject} - {class_name}")
        
        # Step 1: Fetch curriculum data
        log_section("FETCHING CURRICULUM DATA")
        curriculum_data = await fetch_curriculum_data(teacher_id, subject, class_name)
        
        if not curriculum_data:
            detail_logger.error("No curriculum data found")
            raise Exception(f"No curriculum data found for {subject} - {class_name}")
        
        detail_logger.info(f"Found curriculum data:")
        detail_logger.info(f"  Strands: {len(curriculum_data.get('strands', []))}")
        detail_logger.info(f"  Substrands: {len(curriculum_data.get('substrands', []))}")
        detail_logger.info(f"  Content Standards: {len(curriculum_data.get('content_standards', []))}")
        detail_logger.info(f"  Indicators: {len(curriculum_data.get('indicators', []))}")
        
        # Step 2: Build AI prompt
        log_section("BUILDING AI PROMPT")
        prompt = build_outline_prompt(
            curriculum_data=curriculum_data,
            subject=subject,
            class_name=class_name,
            education_system=education_system,
            academic_level=academic_level,
            semester_name=semester_name,
            term=term
        )
        
        detail_logger.info(f"Prompt Length: {len(prompt)} characters")
        detail_logger.info("")
        detail_logger.info("=" * 100)
        detail_logger.info("FULL PROMPT CONTENT:")
        detail_logger.info("=" * 100)
        detail_logger.info(prompt)
        detail_logger.info("=" * 100)
        
        # Step 3: Send to AI
        log_section("CALLING AI MODEL")
        detail_logger.info("Sending request to AI...")
        
        outline_content = await call_ai_for_outline(prompt)
        
        detail_logger.info("✅ AI response received")
        detail_logger.info(f"Outline length: {len(outline_content)} characters")
        detail_logger.info("")
        detail_logger.info("=" * 100)
        detail_logger.info("FULL AI RESPONSE:")
        detail_logger.info("=" * 100)
        detail_logger.info(outline_content)
        detail_logger.info("=" * 100)
        
        # Step 4: Store in database
        log_section("STORING OUTLINE IN DATABASE")
        await store_outline_in_db(
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
        
        # Success
        log_section("OUTLINE GENERATION COMPLETED")
        detail_logger.info(f"Status: SUCCESS")
        detail_logger.info(f"Time: {datetime.now().isoformat()}")
        log_separator()
        
        logger.info(f"✅ Outline generated successfully for {subject} - {class_name}")
        
        return {
            "status": "success",
            "message": f"Outline generated for {subject} - {class_name}",
            "outline_length": len(outline_content)
        }
        
    except Exception as e:
        log_section("OUTLINE GENERATION FAILED")
        detail_logger.error(f"Error: {e}")
        detail_logger.error(f"Trace: {traceback.format_exc()}")
        log_separator()
        
        logger.error(f"❌ Outline generation failed: {e}")
        raise


async def fetch_curriculum_data(teacher_id: str, subject: str, class_name: str) -> Dict[str, Any]:
    """
    Fetch curriculum data (strands, substrands, content standards, indicators)
    from the database for a specific teacher, subject, and class.
    """
    from app.core.database import get_db
    from sqlalchemy import text
    
    detail_logger.info("Fetching curriculum data from database...")
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Fetch strands
        strands_result = await db.execute(
            text("""
                SELECT id, strand_name, subject, class_name, 
                       week_number, session_ids, session_details
                FROM strand
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND class_name = :class_name
            """),
            {"teacher_id": teacher_id, "subject": subject, "class_name": class_name}
        )
        strands = [dict(row._mapping) for row in strands_result]
        
        # Fetch substrands with strand name
        substrands_result = await db.execute(
            text("""
                SELECT s.id, s.substrand_name, s.subject, s.class_name,
                       s.week_numbers, s.session_ids, s.session_details,
                       st.strand_name
                FROM substrand s
                JOIN strand st ON s.strand_id = st.id
                WHERE s.teacher_id = :teacher_id
                  AND s.subject = :subject
                  AND s.class_name = :class_name
            """),
            {"teacher_id": teacher_id, "subject": subject, "class_name": class_name}
        )
        substrands = [dict(row._mapping) for row in substrands_result]
        
        # Fetch content standards with strand and substrand names
        standards_result = await db.execute(
            text("""
                SELECT cs.id, cs.content_standard_code,
                       cs.content_standard, cs.subject, cs.class_name,
                       cs.session_ids, cs.session_details,
                       st.strand_name, s.substrand_name
                FROM contentstandard cs
                JOIN substrand s ON cs.substrand_id = s.id
                JOIN strand st ON s.strand_id = st.id
                WHERE cs.teacher_id = :teacher_id
                  AND cs.subject = :subject
                  AND cs.class_name = :class_name
            """),
            {"teacher_id": teacher_id, "subject": subject, "class_name": class_name}
        )
        content_standards = [dict(row._mapping) for row in standards_result]
        
        # Fetch indicators with all parent names
        indicators_result = await db.execute(
            text("""
                SELECT i.id, i.indicator_code, i.indicator_text, i.subject, i.class_name,
                       i.session_ids, i.session_details,
                       cs.content_standard_code, s.substrand_name, st.strand_name
                FROM indicator i
                JOIN contentstandard cs ON i.content_standard_id = cs.id
                JOIN substrand s ON cs.substrand_id = s.id
                JOIN strand st ON s.strand_id = st.id
                WHERE i.teacher_id = :teacher_id
                  AND i.subject = :subject
                  AND i.class_name = :class_name
            """),
            {"teacher_id": teacher_id, "subject": subject, "class_name": class_name}
        )
        indicators = [dict(row._mapping) for row in indicators_result]
        
        detail_logger.info(f"✅ Fetched {len(strands)} strands, {len(substrands)} substrands, "
                          f"{len(content_standards)} content standards, {len(indicators)} indicators")
        
        return {
            "strands": strands,
            "substrands": substrands,
            "content_standards": content_standards,
            "indicators": indicators
        }
        
    finally:
        await db_gen.aclose()


def build_outline_prompt(
    curriculum_data: Dict[str, Any],
    subject: str,
    class_name: str,
    education_system: Optional[str],
    academic_level: Optional[str],
    semester_name: Optional[str],
    term: Optional[str]
) -> str:
    """
    Build AI prompt for course/subject outline generation.
    Now requests structured JSON matching the new course_outlines table schema.
    """
    strands = curriculum_data.get("strands", [])
    substrands = curriculum_data.get("substrands", [])
    content_standards = curriculum_data.get("content_standards", [])
    indicators = curriculum_data.get("indicators", [])
    
    # Build curriculum summary
    curriculum_summary = []
    
    for strand in strands:
        curriculum_summary.append(f"\n## {strand['strand_name']}")
        
        # Find substrands for this strand
        strand_substrands = [s for s in substrands if s['strand_name'] == strand['strand_name']]
        
        for substrand in strand_substrands:
            curriculum_summary.append(f"\n### {substrand['substrand_name']}")
            
            # Find content standards for this substrand
            substrand_standards = [cs for cs in content_standards 
                                  if cs['strand_name'] == strand['strand_name'] 
                                  and cs['substrand_name'] == substrand['substrand_name']]
            
            for standard in substrand_standards:
                curriculum_summary.append(f"\\n**{standard['content_standard_code']}**: {standard['content_standard']}")
                
                # Find indicators for this standard
                standard_indicators = [i for i in indicators 
                                      if i['content_standard_code'] == standard['content_standard_code']]
                
                for indicator in standard_indicators:
                    curriculum_summary.append(f"- {indicator['indicator_code']}: {indicator['indicator_text']}")
    
    curriculum_text = "\n".join(curriculum_summary)
    
    # Determine terminology based on academic level
    is_university = academic_level and 'university' in academic_level.lower()
    term_type = "Course" if is_university else "Subject"
    role_type = "Lecturer" if is_university else "Teacher"
    
    prompt = f"""You are an expert educational curriculum designer. Create a comprehensive {term_type.lower()} outline based on the provided curriculum structure.

**{term_type.upper()} INFORMATION:**
- {term_type}: {subject}
- Class/Level: {class_name}
- Education System: {education_system or 'General'}
- Academic Level: {academic_level or 'K-12'}
- Semester/Term: {semester_name or term or 'Not specified'}

**CURRICULUM STRUCTURE:**
{curriculum_text}

**YOUR TASK:**
Generate a comprehensive {term_type.lower()} outline in **STRICT JSON FORMAT** with the following structure:

{{
  "terminology": {{
    "type": "{term_type}",
    "role": "{role_type}"
  }},
  "schoolInfoHeaders": [
    "School/University Name",
    "Department/Faculty Name",
    "Program Name"
  ],
  "lectureInfo": {{
    "left": [
      {{"label": "{term_type} Code", "value": ""}},
      {{"label": "{term_type} Title", "value": "{subject}"}},
      {{"label": "{term_type} {role_type}", "value": ""}},
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
    "First learning objective based on curriculum",
    "Second learning objective",
    "Third learning objective",
    "... (3-8 objectives total)"
  ],
  "courseDescription": "A comprehensive 2-3 paragraph description of the {term_type.lower()}, explaining what students will learn, the importance of the subject, and how it fits into the broader curriculum. Base this on the strands and content standards provided.",
  "learningOutcomes": [
    "By the end of this {term_type.lower()}, students will be able to...",
    "Students will demonstrate...",
    "Students will apply...",
    "... (4-10 outcomes total)"
  ],
  "courseDelivery": "Describe the teaching methods and delivery approaches. Include: lectures, practical sessions, group work, projects, assessments, and any technology or resources to be used. Make it specific to {subject}.",
  "courseContent": [
    {{"topic": "Week 1 topic from first strand/substrand", "activity": "Suggested teaching activity"}},
    {{"topic": "Week 2 topic", "activity": "Activity"}},
    {{"topic": "Week 3 topic", "activity": "Activity"}},
    "... (Generate 12-16 weeks of content based on the curriculum structure)"
  ],
  "policies": [
    "Attendance policy appropriate for this level",
    "Academic integrity policy",
    "Late submission policy",
    "Assessment policy",
    "... (4-8 policies total)"
  ]
}}

**CRITICAL INSTRUCTIONS:**
1. Return ONLY valid JSON - no markdown, no code blocks, no explanations
2. Use the EXACT field names shown above (case-sensitive)
3. For courseContent: Create 12-16 week entries mapping the curriculum strands/substrands to a logical weekly progression
4. Each week's "topic" should reference specific content from the curriculum structure provided
5. Each week's "activity" should suggest appropriate teaching/learning activities
6. Make courseObjectives and learningOutcomes specific to the curriculum content provided
7. Ensure all text is professional and appropriate for {academic_level or 'K-12'} level
8. Fill in reasonable defaults for empty fields in lectureInfo (leave value as empty string if truly unknown)
9. Make the courseDescription comprehensive and engaging
10. Policies should be realistic and appropriate for the education level

**REMEMBER:** Return ONLY the JSON object. No preamble, no explanation, no markdown formatting.
"""
    
    return prompt


async def call_ai_for_outline(prompt: str) -> str:
    """
    Call AI model via Vertex AI to generate course outline with retry logic for quota errors.
    """
    from app.core.config import settings
    import time
    import aiohttp
    import json as json_lib
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    from datetime import datetime, timedelta
    
    detail_logger.info("Authenticating with Vertex AI...")
    
    # Retry configuration
    max_retries = 5
    max_auth_retries = 5
    auth_retry_delay = 2
    access_token = None
    
    # Authenticate with Vertex AI
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
                auth_retry_delay *= 2
            else:
                detail_logger.error(f"❌ Failed to authenticate after {max_auth_retries} attempts")
                raise Exception(f"Failed to authenticate with Vertex AI: {e}")
    
    if not access_token:
        raise Exception("Failed to obtain access token")
    
    # Use Vertex AI endpoint
    # Use Vertex AI endpoint
    project_id = settings.GCS_PROJECT_ID
    model_id = "gemini-2.5-flash"  # Updated to match working implementation
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
    
    detail_logger.info(f"🔗 Sending request to Vertex AI: {model_id}")
    
    # Create payload - Note: No Google search for outline as it uses local DB
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generation_config": {
            "temperature": 0.5,
            "maxOutputTokens": 65536  # Increased token limit for comprehensive outlines
        }
    }
    
    # Set headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Retry loop for API calls
    attempt = 0
    retry_delay = 20
    
    while attempt < max_retries:
        try:
            if attempt > 0:
                detail_logger.info(f"🔄 Retry attempt {attempt + 1}/{max_retries}...")
                time.sleep(retry_delay)
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
                                return result_text.strip()
                            else:
                                detail_logger.warning("No content parts found in response")
                                return ""
                        else:
                            detail_logger.warning("No candidates found in response")
                            return ""
                    
                    # Handle 429 rate limit
                    elif response.status == 429:
                        attempt += 1
                        
                        if attempt < max_retries:
                            quota_wait_time = 10 * attempt
                            detail_logger.warning(f"⚠️ Quota/rate limit hit (429). Retrying in {quota_wait_time}s... (Attempt {attempt}/{max_retries})")
                            time.sleep(quota_wait_time)
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
                            time.sleep(retry_delay)
                            continue
                        raise Exception(f"AI API request failed with status {response.status}")
        
        except asyncio.TimeoutError:
            attempt += 1
            if attempt < max_retries:
                detail_logger.warning(f"⏱️ Request timed out. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise Exception("AI request timed out after multiple attempts")
                
        except Exception as e:
            detail_logger.error(f"💥 Error during AI call: {e}")
            attempt += 1
            if attempt < max_retries:
                detail_logger.info(f"   Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise
                
    raise Exception("Failed to generate outline after max retries")





async def store_outline_in_db(
    teacher_id: str,
    subject: str,
    class_name: str,
    outline_content: str,
    education_system: Optional[str],
    academic_level: Optional[str],
    semester_name: Optional[str],
    term: Optional[str]
):
    """
    Store generated outline in database.
    Parses JSON response and stores in new course_outlines table structure.
    """
    from app.core.database import get_db
    from app.models.model import Outline
    from sqlalchemy import delete, and_
    import json as json_lib
    
    detail_logger.info("Parsing AI response...")
    
    # Strip markdown code blocks if present
    cleaned_content = outline_content.strip()
    if cleaned_content.startswith("```json"):
        detail_logger.info("   Detected markdown code block, stripping...")
        # Remove ```json from start and ``` from end
        cleaned_content = cleaned_content[7:]  # Remove ```json
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]  # Remove ```
        cleaned_content = cleaned_content.strip()
    elif cleaned_content.startswith("```"):
        detail_logger.info("   Detected generic code block, stripping...")
        # Remove ``` from start and end
        cleaned_content = cleaned_content[3:]
        if cleaned_content.endswith("```"):
            cleaned_content = cleaned_content[:-3]
        cleaned_content = cleaned_content.strip()
    
    try:
        # Parse JSON response
        outline_data = json_lib.loads(cleaned_content)
        detail_logger.info("✅ JSON parsed successfully")
        detail_logger.info(f"   Keys found: {list(outline_data.keys())}")
    except json_lib.JSONDecodeError as e:
        detail_logger.error(f"❌ Failed to parse JSON: {e}")
        detail_logger.error(f"   Response preview: {cleaned_content[:500]}...")
        raise Exception(f"AI returned invalid JSON: {e}")
    
    # Validate required fields
    required_fields = ['terminology', 'courseObjectives', 'courseDescription', 
                      'learningOutcomes', 'courseDelivery', 'courseContent', 'policies']
    missing_fields = [f for f in required_fields if f not in outline_data]
    
    if missing_fields:
        detail_logger.warning(f"⚠️ Missing fields in AI response: {missing_fields}")
        # Add defaults for missing fields
        if 'terminology' not in outline_data:
            outline_data['terminology'] = {"type": "Subject", "role": "Teacher"}
        if 'courseObjectives' not in outline_data:
            outline_data['courseObjectives'] = [""]
        if 'learningOutcomes' not in outline_data:
            outline_data['learningOutcomes'] = [""]
        if 'policies' not in outline_data:
            outline_data['policies'] = [""]
        if 'courseContent' not in outline_data:
            outline_data['courseContent'] = []
        if 'courseDescription' not in outline_data:
            outline_data['courseDescription'] = ""
        if 'courseDelivery' not in outline_data:
            outline_data['courseDelivery'] = ""
    
    detail_logger.info("Connecting to database...")
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Delete existing outline for same teacher/subject/class
        detail_logger.info("Checking for existing outline...")
        
        delete_stmt = delete(Outline).where(
            and_(
                Outline.teacher_id == UUID(teacher_id),
                Outline.subject_name == subject,
                Outline.class_name == class_name
            )
        )
        
        result = await db.execute(delete_stmt)
        if result.rowcount > 0:
            detail_logger.info(f"Deleted {result.rowcount} existing outline(s)")
        
        # Create new outline with structured data
        detail_logger.info("Creating new outline record...")
        
        # Extract and transform data
        terminology = outline_data.get('terminology', {})
        school_headers = outline_data.get('schoolInfoHeaders', ["", "", ""])
        lecture_info = outline_data.get('lectureInfo', {"left": [], "right": []})
        objectives = outline_data.get('courseObjectives', [""])
        description = outline_data.get('courseDescription', "")
        outcomes = outline_data.get('learningOutcomes', [""])
        delivery = outline_data.get('courseDelivery', "")
        content = outline_data.get('courseContent', [])
        policies = outline_data.get('policies', [""])
        
        # Ensure content has week numbers
        for idx, item in enumerate(content):
            if isinstance(item, dict) and 'week' not in item:
                item['week'] = idx + 1
        
        new_outline = Outline(
            teacher_id=UUID(teacher_id),
            terminology_type=terminology.get('type', 'Subject'),
            terminology_role=terminology.get('role', 'Teacher'),
            school_info_headers=school_headers,
            lecture_info=lecture_info,
            course_objectives=objectives,
            course_description=description,
            learning_outcomes=outcomes,
            course_delivery=delivery,
            course_content=content,
            policies=policies,
            subject_name=subject,
            class_name=class_name,
            academic_year=semester_name,  # Map semester_name to academic_year
            semester=term,  # Map term to semester
            status='draft',
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_outline)
        await db.commit()
        await db.refresh(new_outline)
        
        detail_logger.info(f"✅ Outline stored with ID: {new_outline.id}")
        detail_logger.info(f"   Terminology: {new_outline.terminology_type}/{new_outline.terminology_role}")
        detail_logger.info(f"   Objectives: {len(objectives)}")
        detail_logger.info(f"   Outcomes: {len(outcomes)}")
        detail_logger.info(f"   Content Weeks: {len(content)}")
        detail_logger.info(f"   Policies: {len(policies)}")
        
        # Verify storage
        from sqlmodel import select
        verify_result = await db.execute(
            select(Outline).where(
                and_(
                    Outline.teacher_id == UUID(teacher_id),
                    Outline.subject_name == subject,
                    Outline.class_name == class_name
                )
            )
        )
        stored_outline = verify_result.scalar_one_or_none()
        
        if stored_outline:
            detail_logger.info(f"✅ Verification successful: Outline ID {stored_outline.id}")
        else:
            raise Exception("Verification failed: Outline not found after storage")
        
    finally:
        await db_gen.aclose()
