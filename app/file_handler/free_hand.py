"""
Free Plan Handler - API Endpoint for Document-Free Plan Generation

Allows teachers to generate semester plans using only their input and AI web search,
without uploading any documents.
"""

import logging
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create detailed file logger for API endpoint
log_file = os.path.join(os.path.dirname(__file__), '..', 'free_back', 'log.txt')
endpoint_logger = logging.getLogger('free_plan_endpoint')
endpoint_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - [ENDPOINT] %(message)s')
file_handler.setFormatter(formatter)
endpoint_logger.addHandler(file_handler)

def log_separator():
    """Log a separator line"""
    endpoint_logger.info("=" * 100)

def log_section(title: str):
    """Log a section header"""
    endpoint_logger.info("")
    endpoint_logger.info("=" * 100)
    endpoint_logger.info(f"  {title}")
    endpoint_logger.info("=" * 100)

# Create router
router = APIRouter(prefix="/api/free-plan", tags=["Free Plan"])

# Import dependencies
try:
    from app.core.database import get_db
    from app.models.model import TeacherProfile, AcademicCalendar, ClassSession
    from app.core.dependencies import get_current_teacher
    from app.free_back.enqueue_free import enqueue_free_plan
    logger.info("✅ Free plan handler imports successful")
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    raise


class FreePlanRequest(BaseModel):
    """Request model for free plan generation"""
    subject: str = Field(..., description="Subject or course name")
    class_name: str = Field(..., description="Class name (e.g., 'Class A', 'Section 1')")
    pupils: str = Field(..., description="Pupil/class level (e.g., 'Level 100', 'Grade 4', 'Class 2')")
    academic_level: str = Field(..., description="Academic level: university, college, k12, or other")
    education_system: str = Field(..., description="Education system (e.g., 'Ghana', 'Cambridge', 'IB')")
    topic_description: Optional[str] = Field(None, description="Optional topic to focus on")
    learning_objective: Optional[str] = Field(None, description="Optional learning objectives")


@router.post("/generate")
async def generate_free_plan(
    request: FreePlanRequest,
    session: AsyncSession = Depends(get_db),
    current_teacher: TeacherProfile = Depends(get_current_teacher)
):
    """
    Generate a semester plan using AI and web search without uploading documents.
    
    This endpoint:
    1. Accepts educational context from the teacher
    2. Fetches REAL class sessions from ClassSession table
    3. Enqueues an AI task to search the web for curriculum info
    4. Returns immediately while processing happens in background
    5. Sends WebSocket updates to the frontend
    6. Stores the generated plan in the database
    
    Returns:
        Status message with job details
    """
    try:
        teacher_id = str(current_teacher.id)
        
        # Log API request received
        log_section(f"API REQUEST RECEIVED - {datetime.now().isoformat()}")
        endpoint_logger.info(f"Teacher ID: {teacher_id}")
        endpoint_logger.info(f"Teacher Email: {current_teacher.email if hasattr(current_teacher, 'email') else 'N/A'}")
        endpoint_logger.info(f"Request Timestamp: {datetime.now().isoformat()}")
        
        log_section("REQUEST PARAMETERS")
        endpoint_logger.info(f"Subject: {request.subject}")
        endpoint_logger.info(f"Class Name: {request.class_name}")
        endpoint_logger.info(f"Pupils/Level: {request.pupils}")
        endpoint_logger.info(f"Academic Level: {request.academic_level}")
        endpoint_logger.info(f"Education System: {request.education_system}")
        endpoint_logger.info(f"Topic Description: {request.topic_description if request.topic_description else 'None'}")
        endpoint_logger.info(f"Learning Objective: {request.learning_objective if request.learning_objective else 'None'}")
        
        logger.info("=" * 70)  
        logger.info(f"🆓 [FREE PLAN] Request received from teacher: {teacher_id}")
        logger.info(f"📚 Subject: {request.subject}, Class: {request.class_name}, Pupils: {request.pupils}")
        logger.info(f"🎓 Academic Level: {request.academic_level}")
        logger.info(f"🌍 Education System: {request.education_system}")
        if request.topic_description:
            logger.info(f"📝 Topic: {request.topic_description}")
        if request.learning_objective:
            logger.info(f"🎯 Objectives: {request.learning_objective}")
        logger.info("=" * 70)
        
        # Gather session data from ClassSession table (matching semplan implementation)
        session_data = None
        try:
            log_section("GATHERING SESSION DATA")
            endpoint_logger.info("Fetching academic calendar...")
            
            # Get academic calendar
            calendar_result = await session.execute(
                select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
            )
            calendar = calendar_result.scalar_one_or_none()
            
            if not calendar:
                endpoint_logger.error("❌ No academic calendar found")
                raise HTTPException(
                    status_code=404,
                    detail="No academic calendar found. Please set up your calendar first."
                )
            
            endpoint_logger.info(f"✅ Academic calendar found")
            endpoint_logger.info(f"   Semester Start: {calendar.semester_start_date if calendar.semester_start_date else 'N/A'}")
            endpoint_logger.info(f"   Semester End: {calendar.semester_end_date if calendar.semester_end_date else 'N/A'}")
            endpoint_logger.info(f"   Semester Name: {calendar.semester_name if hasattr(calendar, 'semester_name') else 'N/A'}")
            
            endpoint_logger.info("Fetching class sessions...")
            endpoint_logger.info(f"Querying DB for: Subject={request.subject}, Class={request.class_name}")
            endpoint_logger.info(f"AI Targeting: Pupils={request.pupils}")
            
            # Get actual class sessions (with real IDs and dates) - matching semplan
            sessions_result = await session.execute(
                select(ClassSession).where(
                    (ClassSession.subject.ilike(f"%{request.subject}%")) &
                    (ClassSession.class_name.ilike(f"%{request.class_name}%")) &
                    (ClassSession.teacher_id == current_teacher.id)
                )
            )
            class_sessions = sessions_result.scalars().all()
            
            if not class_sessions:
                endpoint_logger.error(f"❌ No class sessions found for {request.subject} - {request.class_name}")
                raise HTTPException(
                    status_code=404,
                    detail=f"No class sessions found for {request.subject} - {request.class_name}. Please create sessions in your timetable first."
                )
            
            endpoint_logger.info(f"✅ Found {len(class_sessions)} class sessions")
            
            # Log details of sessions for debugging
            for i, session_obj in enumerate(class_sessions[:3]):  # Show first 3
                endpoint_logger.info(f"   Session {i+1}: ID={session_obj.id}, Date={session_obj.date}, "
                                   f"Start={session_obj.start_time}, End={session_obj.end_time}")
            
            log_section("FORMATTING SESSION DATA")
            endpoint_logger.info("Grouping sessions by week...")
            
            # Group sessions by week (matching semplan implementation)
            sessions_by_week = {}
            
            for session_obj in class_sessions:
                # Calculate week number based on academic calendar start date
                days_diff = (session_obj.date - calendar.semester_start_date).days
                week_number = (days_diff // 7) + 1
                
                # Ensure week number is valid
                if 1 <= week_number <= 20:  # Allow up to 20 weeks
                    week_key = f"Week {week_number}"
                    
                    if week_key not in sessions_by_week:
                        sessions_by_week[week_key] = {
                            "week_number": week_number,
                            "sessions": []
                        }
                    
                    # Create session info with REAL session ID from ClassSession table
                    session_info = {
                        "id": session_obj.id,  # ← Real ClassSession ID (not generated)
                        "date": str(session_obj.date),
                        "subject": session_obj.subject,
                        "start_time": str(session_obj.start_time),
                        "end_time": str(session_obj.end_time),
                        "class_name": session_obj.class_name,
                        "location": session_obj.location,
                        "session_number": session_obj.session_number,
                        "week_number": week_number
                    }
                    
                    sessions_by_week[week_key]["sessions"].append(session_info)
                else:
                    endpoint_logger.warning(f"Session {session_obj.id} (date: {session_obj.date}) falls outside valid week range, calculated week: {week_number}")
            
            endpoint_logger.info(f"✅ Session data formatted:")
            endpoint_logger.info(f"   Total weeks: {len(sessions_by_week)}")
            endpoint_logger.info(f"   Total sessions: {len(class_sessions)}")
            
            # Calculate sessions per week (average)
            if sessions_by_week:
                avg_sessions = len(class_sessions) / len(sessions_by_week)
                endpoint_logger.info(f"   Avg sessions per week: {avg_sessions:.1f}")
            
            endpoint_logger.info(f"   Weeks: {list(sessions_by_week.keys())}")
            for week_key in list(sessions_by_week.keys())[:3]:  # Show first 3 weeks
                endpoint_logger.info(f"      {week_key}: {len(sessions_by_week[week_key]['sessions'])} sessions")
            
            session_data = {
                "semester_start_date": calendar.semester_start_date.isoformat() if calendar.semester_start_date else None,
                "semester_end_date": calendar.semester_end_date.isoformat() if calendar.semester_end_date else None,
                "weekly_sessions": sessions_by_week
            }
            
            logger.info(f"✅ Gathered session data: {len(sessions_by_week)} weeks, {len(class_sessions)} sessions")
            
        except HTTPException:
            raise
        except Exception as e:
            endpoint_logger.error(f"❌ Error gathering session data: {e}")
            endpoint_logger.error(f"   Exception type: {type(e).__name__}")
            logger.error(f"❌ Error gathering session data: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to gather session data: {str(e)}")
        
        # Enqueue the free plan task
        try:
            log_section("ENQUEUEING BACKGROUND TASK")
            endpoint_logger.info("Preparing to enqueue AI generation task...")
            endpoint_logger.info(f"Teacher ID: {teacher_id}")
            endpoint_logger.info(f"Subject: {request.subject}")
            endpoint_logger.info(f"Class: {request.class_name}")
            endpoint_logger.info(f"Pupils: {request.pupils}")
            endpoint_logger.info(f"Academic Level: {request.academic_level}")
            endpoint_logger.info(f"Education System: {request.education_system}")
            endpoint_logger.info(f"Delay: 2 seconds")
            
            job = await enqueue_free_plan(
                teacher_id=teacher_id,
                subject=request.subject,
                class_name=request.class_name,
                pupils=request.pupils,
                academic_level=request.academic_level,
                education_system=request.education_system,
                session_data=session_data,
                topic_description=request.topic_description,
                learning_objective=request.learning_objective,
                delay=2  # Small delay to ensure response is sent first
            )
            
            if not job:
                endpoint_logger.error("❌ Failed to enqueue task - job returned None")
                raise HTTPException(status_code=500, detail="Failed to enqueue plan generation task")
            
            endpoint_logger.info(f"✅ Task enqueued successfully")
            endpoint_logger.info(f"   Job ID: {job.job_id}")
            endpoint_logger.info(f"   Queue: free_plan_queue")
            endpoint_logger.info(f"   Status: Queued")
            
            logger.info(f"✅ Free plan task enqueued - Job ID: {job.job_id}")
            
            log_section("API RESPONSE PREPARATION")
            response_data = {
                "status": "success",
                "message": f"Plan generation started for {request.subject} - {request.pupils}",
                "job_id": job.job_id,
                "details": {
                    "subject": request.subject,
                    "class_name": request.class_name,
                    "pupils": request.pupils,
                    "academic_level": request.academic_level,
                    "education_system": request.education_system,
                    "topic": request.topic_description,
                    "objectives": request.learning_objective,
                    "weeks": len(sessions_by_week),
                    "sessions": len(class_sessions)
                }
            }
            
            endpoint_logger.info("Response prepared:")
            endpoint_logger.info(f"   Status: {response_data['status']}")
            endpoint_logger.info(f"   Job ID: {response_data['job_id']}")
            endpoint_logger.info(f"   Weeks: {response_data['details']['weeks']}")
            endpoint_logger.info(f"   Sessions: {response_data['details']['sessions']}")
            
            log_section("API REQUEST COMPLETED SUCCESSFULLY")
            endpoint_logger.info(f"Request processing time: {datetime.now().isoformat()}")
            endpoint_logger.info("Background task queued - waiting for worker to pick up")
            log_separator()
            
            return response_data
            
        except HTTPException:
            raise
        except Exception as e:
            endpoint_logger.error(f"❌ Error enqueueing task: {e}")
            endpoint_logger.error(f"   Exception type: {type(e).__name__}")
            log_separator()
            logger.error(f"❌ Error enqueueing task: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to start plan generation: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        endpoint_logger.error(f"❌ Unexpected error in endpoint: {e}")
        endpoint_logger.error(f"   Exception type: {type(e).__name__}")
        log_separator()
        logger.error(f"❌ Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include router in main app
def get_router():
    """Get the router for inclusion in main app"""
    return router
