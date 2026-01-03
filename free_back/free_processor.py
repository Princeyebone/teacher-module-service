"""
Free Plan Processor - Generate semester plans without documents

This module provides AI-powered semester plan generation using only teacher input
and web search. No document upload required.
"""

import os
import json
import logging
import traceback
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create detailed file logger
log_file = os.path.join(os.path.dirname(__file__), 'log.txt')
detail_logger = logging.getLogger('free_plan_detail')
detail_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
detail_logger.addHandler(file_handler)

def log_separator():
    """Log a separator line"""
    detail_logger.info("=" * 100)

def log_section(title: str):
    """Log a section header"""
    detail_logger.info("")
    detail_logger.info("=" * 100)
    detail_logger.info(f"  {title}")
    detail_logger.info("=" * 100)

# Import database and models
try:
    from database import get_db
    from model import Strand, Substrand, ContentStandard, Indicator
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, and_, delete
    logger.info("✅ Database imports successful")
except ImportError as e:
    logger.error(f"❌ Database import error: {e}")
    raise

# Import AI service
try:
    from external_service import send_semester_plan_to_ai
    logger.info("✅ AI service import successful")
except ImportError as e:
    logger.error(f"❌ AI service import error: {e}")
    raise

# Import WebSocket functions
try:
    from sch_ground.background import publish_ws_message, save_notification
    logger.info("✅ WebSocket imports successful")
except ImportError as e:
    logger.error(f"❌ WebSocket import error: {e}")
    async def publish_ws_message(teacher_id: str, message: dict):
        logger.info(f"[MOCK WS] {teacher_id}: {message}")
    async def save_notification(**kwargs):
        logger.info(f"[MOCK NOTIF] {kwargs}")


def build_free_plan_prompt(
    subject: str,
    class_name: str,
    pupils: str,
    academic_level: str,
    education_system: str,
    session_data: dict = None,
    topic_description: str = None,
    learning_objective: str = None,
    semester_name: str = None,
    term: str = None
) -> str:
    """
    Build a prompt for AI-powered free plan generation without documents.
    Uses web search exclusively to find curriculum information.
    
    Args:
        subject: Subject/Course name
        class_name: Class name/section
        pupils: Pupil/Class level (e.g., "Level 100", "Grade 4")
        academic_level: Academic level (university/college/k12/other)
        education_system: Education system
        session_data: Session data with weekly sessions
        topic_description: Optional topic to focus on
        learning_objective: Optional learning objectives
        semester_name: Current semester
        term: Current term
        
    Returns:
        Structured prompt for AI
    """
    # Format session data
    available_weeks = []
    week_details = []
    
    if session_data and 'weekly_sessions' in session_data:
        available_weeks = list(session_data['weekly_sessions'].keys())
        for week_key, week_data in session_data['weekly_sessions'].items():
            session_count = len(week_data.get('sessions', []))
            week_details.append(f"{week_key}: {session_count} sessions")
    
    # Build topic and objective sections
    topic_section = ""
    if topic_description:
        topic_section = f"""
TOPIC FOCUS:
The plan should focus on this topic: {topic_description}
Ensure all content relates to this topic."""

    objective_section = ""
    if learning_objective:
        objective_section = f"""
LEARNING OBJECTIVES:
The plan must meet these learning objectives:
{learning_objective}

Ensure all strands, substrands, content standards, and indicators align with these objectives."""

    example_json = '''{
  "strand_data": [...],
  "substrand_data": [...],
  "content_standard_data": [...],
  "indicator_data": [...]
}'''

    prompt = f"""You are an Educational Curriculum Planning AI with web search capabilities. Create a comprehensive semester plan by searching the web for official curriculum information.

**CRITICAL**: You MUST use web search to find the curriculum information. There are NO local documents provided.

WEB SEARCH REQUIREMENTS (MANDATORY):
You MUST search the web for:
- Official curriculum documents for {education_system} education system
- {academic_level} level curriculum for {subject}
- **{semester_name if semester_name else 'Current semester'}** curriculum for {pupils} in {subject}
- Syllabus for {pupils} (pupil level) in {subject} - **{semester_name if semester_name else 'semester'} specific**
- {pupils} level teaching content for {subject} - **{semester_name if semester_name else 'semester'} {term if term else ''} term**
- Strands, substrands, content standards, and indicators for {pupils} - **{semester_name if semester_name else 'semester'}**
- Week-by-week teaching plans and learning outcomes for {pupils} - **{semester_name if semester_name else 'semester'}**
- {education_system} {semester_name if semester_name else 'semester'} {term if term else ''} syllabus for {pupils}

EDUCATIONAL CONTEXT:
- Education System: {education_system}
- Academic Level: {academic_level}
- Subject/Course: {subject}
- **PUPIL/CLASS LEVEL: {pupils}** ← PRIMARY level indicator for curriculum targeting
- **SEMESTER: {semester_name if semester_name else "Not specified"}** ← CRITICAL for temporal targeting
- **TERM: {term if term else "Not specified"}** ← Additional temporal context
{topic_section}
{objective_section}

AVAILABLE TEACHING SESSIONS:
{json.dumps(session_data, indent=2) if session_data else "No session data provided"}

AVAILABLE WEEKS: {', '.join(available_weeks) if available_weeks else "None"}
WEEK DETAILS: {', '.join(week_details) if week_details else "No weeks available"}

INSTRUCTIONS:
1. SEARCH THE WEB for the official curriculum structure for this educational context
2. Identify appropriate strands, substrands, content standards, and indicators
3. Map these to the available teaching sessions
4. Use ONLY the weeks and sessions provided in WeeklySessions data
5. If topic description is provided, ensure content relates to it
6. If learning objectives are provided, ensure all elements support them
7. Week numbers MUST be NUMERIC VALUES ONLY (e.g., [1, 2, 3])
8. Return FLAT STRUCTURES for all curriculum elements
9. Use strand_name, substrand_name, content_standard_text, indicator_text (NOT "name")

CONTENT ASSIGNMENT RULES:
1. Each content standard MUST be assigned to sessions
2. Each indicator MUST be assigned to sessions  
3. Maximum TWO indicators per session
4. Even distribution across available sessions

EXPECTED OUTPUT FORMAT:
{example_json}

Return ONLY the JSON, nothing else. DO NOT wrap in markdown code blocks.
"""
    
    return prompt


async def process_free_plan_task(
    ctx: dict,
    teacher_id: str,
    subject: str,
    class_name: str,
    pupils: str,
    academic_level: str,
    education_system: str,
    session_data: Dict = None,
    topic_description: str = None,
    learning_objective: str = None
):
    """
    Generate a semester plan using only teacher input and web search.
    
    Args:
        ctx: ARQ context
        teacher_id: Teacher UUID
        subject: Subject/Course name
        class_name: Class name/section
        pupils: Pupil/Class level (e.g., "Level 100", "Grade 4")
        academic_level: Academic level (university/college/k12/other)
        education_system: Education system
        session_data: Session data with weeks and sessions
        topic_description: Optional topic focus
        learning_objective: Optional learning objectives
        
    Returns:
        Dict with processing results
    """
    logger.info("=" * 60)
    logger.info(f"🆓 [FREE PLAN] Starting free plan generation for teacher {teacher_id}")
    logger.info(f"📚 Subject: {subject}, Class: {class_name}, Pupils: {pupils}")
    logger.info(f"🎓 Academic Level: {academic_level}, Education System: {education_system}")
    logger.info("=" * 60)
    
    # Detailed logging
    log_section(f"FREE PLAN GENERATION STARTED - {datetime.now().isoformat()}")
    detail_logger.info(f"Teacher ID: {teacher_id}")
    detail_logger.info(f"Subject: {subject}")
    detail_logger.info(f"Class: {class_name}")
    detail_logger.info(f"Pupils/Level: {pupils}")
    detail_logger.info(f"Academic Level: {academic_level}")
    detail_logger.info(f"Education System: {education_system}")
    detail_logger.info(f"Topic Description: {topic_description if topic_description else 'None'}")
    detail_logger.info(f"Learning Objective: {learning_objective if learning_objective else 'None'}")
    
    # Log session data
    log_section("INPUT: SESSION DATA")
    if session_data:
        detail_logger.info(json.dumps(session_data, indent=2, default=str))
    else:
        detail_logger.info("⚠️ No session data provided")
    
    try:
        # Send initial status
        await publish_ws_message(teacher_id, {
            "type": "semplan_processing",
            "status": "started",
            "message": f"Starting AI-powered plan generation for {subject} - {class_name}",
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name,
            "source": "free_plan"
        })
        
        # Get database session
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Fetch semester metadata
            semester_name = None
            term = None
            
            log_section("FETCHING SEMESTER METADATA")
            try:
                from model import AcademicCalendar
                from sqlalchemy import select
                calendar_result = await db.execute(
                    select(AcademicCalendar).where(AcademicCalendar.teacher_id == UUID(teacher_id))
                )
                calendar = calendar_result.scalar_one_or_none()
                
                if calendar:
                    semester_name = calendar.semester_name if hasattr(calendar, 'semester_name') else None
                    term = calendar.term if hasattr(calendar, 'term') else None
                    detail_logger.info(f"Semester: {semester_name}, Term: {term}")
                else:
                    detail_logger.warning("No AcademicCalendar found")
            except Exception as e:
                detail_logger.error(f"Error fetching calendar: {e}")
            
            # Build prompt with web search instructions
            log_section("BUILDING AI PROMPT WITH WEB SEARCH")
            
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "processing",
                "message": "🌐 Searching web for curriculum information...",
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            prompt = build_free_plan_prompt(
                subject=subject,
                class_name=class_name,
                pupils=pupils,
                academic_level=academic_level,
                education_system=education_system,
                session_data=session_data,
                topic_description=topic_description,
                learning_objective=learning_objective,
                semester_name=semester_name,
                term=term
            )
            
            detail_logger.info(f"Prompt Length: {len(prompt)} characters")
            detail_logger.info(f"Prompt Content:\n{prompt}")
            
            # Log web search configuration
            log_section("WEB SEARCH CONFIGURATION")
            detail_logger.info("Web Search: MANDATORY (no local documents)")
            detail_logger.info(f"Search Context - Education System: {education_system}")
            detail_logger.info(f"Search Context - Academic Level: {academic_level}")
            detail_logger.info(f"Search Context - Subject: {subject}")
            detail_logger.info(f"Search Context - Pupils/Level: {pupils} ← PRIMARY TARGETING")
            detail_logger.info(f"Search Context - **SEMESTER: {semester_name if semester_name else 'Not specified'}** ← TEMPORAL TARGETING")
            detail_logger.info(f"Search Context - Term: {term if term else 'Not specified'}")
            detail_logger.info(f"Search Context - Topic: {topic_description if topic_description else 'Any'}")
            detail_logger.info(f"Search Context - Objectives: {learning_objective if learning_objective else 'General'}")
            
            # Send to AI
            detail_logger.info("Sending to AI with web search...")
            from config import settings
            ai_response = await send_semester_plan_to_ai(
                prompt,
                f"free://ai_generated/{subject}/{class_name}",
                settings.API_KEY,
                session_data,
                class_name,
                subject
            )
            
            # Log AI response
            log_section("AI RESPONSE")
            if not ai_response or "error" in ai_response:
                error_msg = ai_response.get("error", "Failed") if ai_response else "No response"
                detail_logger.error(f"AI Error: {error_msg}")
                
                await publish_ws_message(teacher_id, {
                    "type": "semplan_processing",
                    "status": "error",
                    "message": f"AI processing failed: {error_msg}",
                    "teacher_id": teacher_id,
                    "subject": subject,
                    "class_name": class_name
                })
                return {"status": "error", "message": error_msg}
            
            detail_logger.info("✅ AI Processing Successful")
            detail_logger.info(f"Response Length: {len(str(ai_response))} characters")
            detail_logger.info(f"Strands: {len(ai_response.get('strand_data', []))}")
            detail_logger.info(f"Substrands: {len(ai_response.get('substrand_data', []))}")
            detail_logger.info(f"Content Standards: {len(ai_response.get('content_standard_data', []))}")
            detail_logger.info(f"Indicators: {len(ai_response.get('indicator_data', []))}")
            detail_logger.info(f"\nComplete Response:\n{json.dumps(ai_response, indent=2, default=str)}")
            
            # Check for existing plan and delete if found
            log_section("CHECKING FOR EXISTING PLAN")
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "checking",
                "message": "Checking for existing plan...",
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            try:
                # Check if plan already exists for this teacher, subject, and class_name
                from sqlalchemy import select, and_, delete
                existing_strands = await db.execute(
                    select(Strand).where(
                        and_(
                            Strand.teacher_id == UUID(teacher_id),
                            Strand.subject == subject,
                            Strand.class_name == class_name
                        )
                    )
                )
                existing_strands_list = existing_strands.scalars().all()
                
                if existing_strands_list:
                    detail_logger.info(f"⚠️ Found existing plan for {subject} - {class_name}")
                    detail_logger.info(f"   Existing strands: {len(existing_strands_list)}")
                    
                    await publish_ws_message(teacher_id, {
                        "type": "semplan_processing",
                        "status": "deleting_old",
                        "message": f"Deleting existing plan for {subject} - {class_name}...",
                        "teacher_id": teacher_id,
                        "subject": subject,
                        "class_name": class_name
                    })
                    
                    log_section("DELETING EXISTING PLAN")
                    detail_logger.info(f"Deleting existing plan for teacher={teacher_id}, subject={subject}, class={class_name}")
                    
                    # Delete all related data
                    # Delete Indicators
                    indicators_deleted = await db.execute(
                        delete(Indicator).where(
                            and_(
                                Indicator.teacher_id == UUID(teacher_id),
                                Indicator.subject == subject,
                                Indicator.class_name == class_name
                            )
                        )
                    )
                    detail_logger.info(f"   Deleted {indicators_deleted.rowcount} indicators")
                    
                    # Delete Content Standards
                    standards_deleted = await db.execute(
                        delete(ContentStandard).where(
                            and_(
                                ContentStandard.teacher_id == UUID(teacher_id),
                                ContentStandard.subject == subject,
                                ContentStandard.class_name == class_name
                            )
                        )
                    )
                    detail_logger.info(f"   Deleted {standards_deleted.rowcount} content standards")
                    
                    # Delete Substrands
                    substrands_deleted = await db.execute(
                        delete(Substrand).where(
                            and_(
                                Substrand.teacher_id == UUID(teacher_id),
                                Substrand.subject == subject,
                                Substrand.class_name == class_name
                            )
                        )
                    )
                    detail_logger.info(f"   Deleted {substrands_deleted.rowcount} substrands")
                    
                    # Delete Strands
                    strands_deleted = await db.execute(
                        delete(Strand).where(
                            and_(
                                Strand.teacher_id == UUID(teacher_id),
                                Strand.subject == subject,
                                Strand.class_name == class_name
                            )
                        )
                    )
                    detail_logger.info(f"   Deleted {strands_deleted.rowcount} strands")
                    
                    # Commit the deletions
                    await db.commit()
                    
                    detail_logger.info("✅ Old plan deleted successfully")
                    logger.info(f"🗑️ Deleted existing plan for {subject} - {class_name}")
                else:
                    detail_logger.info(f"✓ No existing plan found for {subject} - {class_name}")
                    detail_logger.info("   Proceeding with fresh storage")
                    
            except Exception as e:
                detail_logger.error(f"❌ Error checking/deleting existing plan: {e}")
                detail_logger.error(f"   Will proceed with storage anyway")
                logger.warning(f"Error checking existing plan: {e}")
            
            # Store in database
            log_section("DATABASE STORAGE")
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "storing",
                "message": "Storing new plan in database...",
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            detail_logger.info("Storing new plan in database...")
            
            # RETRY CONFIGURATION
            max_db_retries = 3
            max_outline_retries = 3
            
            # Storage with retry logic
            db_attempt = 0
            db_retry_delay = 5  # Start with 5 seconds
            storage_success = False
            
            while db_attempt < max_db_retries and not storage_success:
                try:
                    if db_attempt > 0:
                        detail_logger.info(f"🔄 [DB RETRY] Attempt {db_attempt + 1}/{max_db_retries} after {db_retry_delay}s wait...")
                        await asyncio.sleep(db_retry_delay)
                        db_retry_delay *= 2  # Exponential backoff
                    
                    await store_free_plan_in_db(teacher_id, class_name, subject, ai_response, db)
                    detail_logger.info("✅ Storage function completed")
                    storage_success = True
                    
                except Exception as db_error:
                    db_attempt += 1
                    detail_logger.error(f"❌ DB Storage error (attempt {db_attempt}): {db_error}")
                    
                    if db_attempt < max_db_retries:
                        detail_logger.info(f"   Will retry in {db_retry_delay}s...")
                        await db.rollback()
                    else:
                        detail_logger.error(f"❌ DB Storage failed after {max_db_retries} attempts")
                        await db.rollback()
                        raise Exception(f"Database storage failed after {max_db_retries} attempts: {db_error}")
            
            # Generate outline INLINE with retry (same task, same transaction)
            log_section("INLINE OUTLINE GENERATION")
            detail_logger.info("Plan storage successful - generating course outline...")
            
            await publish_ws_message(teacher_id, {
                "type": "semplan_processing",
                "status": "generating_outline",
                "message": f"Generating course outline for {subject} - {class_name}...",
                "teacher_id": teacher_id,
                "subject": subject,
                "class_name": class_name
            })
            
            from outline_back.inline_outline import generate_outline_inline
            
            # Outline generation with retry logic
            outline_attempt = 0
            outline_retry_delay = 10  # Start with 10 seconds
            outline_success = False
            outline_result = None
            
            while outline_attempt < max_outline_retries and not outline_success:
                try:
                    if outline_attempt > 0:
                        detail_logger.info(f"🔄 [OUTLINE RETRY] Attempt {outline_attempt + 1}/{max_outline_retries} after {outline_retry_delay}s wait...")
                        await asyncio.sleep(outline_retry_delay)
                        outline_retry_delay *= 2  # Exponential backoff
                    
                    outline_result = await generate_outline_inline(
                        db=db,
                        teacher_id=teacher_id,
                        subject=subject,
                        class_name=class_name,
                        education_system=education_system,
                        academic_level=academic_level,
                        semester_name=semester_name,
                        term=term
                    )
                    
                    detail_logger.info(f"✅ Outline generated: {outline_result}")
                    logger.info(f"📘 Outline generated for {subject} - {class_name}")
                    outline_success = True
                    
                except Exception as outline_error:
                    outline_attempt += 1
                    detail_logger.error(f"❌ Outline generation error (attempt {outline_attempt}): {outline_error}")
                    
                    if outline_attempt < max_outline_retries:
                        detail_logger.info(f"   Will retry in {outline_retry_delay}s...")
                    else:
                        detail_logger.error(f"❌ Outline generation failed after {max_outline_retries} attempts")
                        await db.rollback()  # Rollback plan if outline fails
                        raise Exception(f"Outline generation failed after {max_outline_retries} attempts: {outline_error}")
            
            # Commit both plan AND outline together (atomic operation)
            await db.commit()
            detail_logger.info("✅ Plan and outline committed to database")
            
        finally:
            await db_gen.aclose()
        
        # Success notification - only sent if BOTH plan AND outline succeeded
        log_section("FREE PLAN + OUTLINE GENERATION COMPLETED")
        detail_logger.info(f"Status: SUCCESS")
        detail_logger.info(f"Time: {datetime.now().isoformat()}")
        log_separator()
        
        await publish_ws_message(teacher_id, {
            "type": "semplan_processing",
            "status": "completed",
            "message": f"Plan and outline created successfully for {subject} - {class_name}",
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name,
            "ai_processed": True,
            "source": "free_plan",
            "outline_generated": True
        })
        
        await save_notification(
            teacher_id=teacher_id,
            title="Plan & Outline Created",
            message=f"Plan and outline for {subject} - {class_name} are ready",
            type_="success"
        )
        
        return {
            "status": "success",
            "message": f"Plan created for {subject} - {class_name}",
            "subject": subject,
            "class_name": class_name
        }
        
    except Exception as e:
        error_msg = f"Free plan generation failed: {str(e)}"
        error_trace = traceback.format_exc()
        
        logger.error(f"❌ {error_msg}")
        logger.error(error_trace)
        
        log_section("FREE PLAN GENERATION FAILED")
        detail_logger.error(f"Error: {error_msg}")
        detail_logger.error(f"Type: {type(e).__name__}")
        detail_logger.error(f"Traceback:\n{error_trace}")
        log_separator()
        
        await publish_ws_message(teacher_id, {
            "type": "semplan_processing",
            "status": "error",
            "message": error_msg,
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name
        })
        
        await save_notification(
            teacher_id=teacher_id,
            title="Plan Generation Failed",
            message=error_msg,
            type_="error"
        )
        
        raise RuntimeError(error_msg)


async def store_free_plan_in_db(
    teacher_id: str,
    class_name: str,
    subject: str,
    ai_response: dict,
    db: AsyncSession
):
    """Store AI-generated plan in database (same as curriculum)"""
    from curri_back.curri_processor import store_ai_response_in_tables
    await store_ai_response_in_tables(teacher_id, class_name, subject, ai_response, db)
