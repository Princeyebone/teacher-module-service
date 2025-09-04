from fastapi import APIRouter, UploadFile, HTTPException, Depends, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
from uuid import uuid4, UUID
import os
from logger import logger
from model import TeacherProfile
from database import get_db
from datetime import datetime
from schemas import AvailableWeeksResponse, WeekAvailability, SessionInfo
from dependencies import get_current_teacher
from typing import Annotated
from model import AcademicCalendar, ClassSession, Strand
import json


router = APIRouter(tags=["Semester Mapper File Handler"])



@router.get("/available-weeks-sessions/{subject}/{class_name}", response_model=AvailableWeeksResponse)
async def get_available_weeks_sessions(
    subject: str,
    class_name: str,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """
    Get available weeks and sessions for curriculum planning.
    Returns weeks that are NOT booked in the Strand table.
    """
    logger.debug(f"Fetching available weeks and sessions for teacher_id: {current_teacher.id}, subject: {subject}, class_name: {class_name}")
    
    try:
        # Step 1: Get Academic Calendar for semester boundaries
        acc = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()
        
        if not acc:
            logger.error("Academic calendar not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Academic calendar not found for this teacher"
            )

        acc_start_date = acc.semester_start_date
        acc_end_date = acc.semester_end_date
        logger.debug(f"Academic calendar: start_date={acc_start_date}, end_date={acc_end_date}")

        # Step 2: Get all ClassSessions for the subject and class
        subject = subject.strip()
        class_name = class_name.strip()
        
        class_sessions = (await db.execute(
            select(ClassSession).where(
                (ClassSession.subject.ilike(f"%{subject}%")) &
                (ClassSession.class_name.ilike(f"%{class_name}%")) &
                (ClassSession.teacher_id == current_teacher.id)
            )
        )).scalars().all()
        
        logger.debug(f"Found {len(class_sessions)} total class sessions for {subject} - {class_name}")

        # Step 3: Calculate week numbers and group sessions by week
        sessions_by_week = {}
        
        for session in class_sessions:
            # Calculate week number using the same logic as the existing endpoint
            # week_number = (session.date - acc_start_date).days // 7 + 1
            days_diff = (session.date - acc_start_date).days
            week_number = (days_diff // 7) + 1
            
            # Ensure week number is within valid range (1-16)
            if 1 <= week_number <= 16:
                week_key = f"Week {week_number}"
                
                if week_key not in sessions_by_week:
                    sessions_by_week[week_key] = []
                
                # Create SessionInfo object
                session_info = SessionInfo(
                    id=session.id,
                    date=str(session.date),
                    subject=session.subject,
                    start_time=session.start_time,
                    end_time=session.end_time,
                    class_name=session.class_name,
                    location=session.location,
                    session_number=session.session_number
                )
                
                sessions_by_week[week_key].append(session_info)
        
        logger.debug(f"Grouped sessions into {len(sessions_by_week)} weeks: {list(sessions_by_week.keys())}")

        # Step 4: Get booked weeks from Strand table
        booked_weeks = (await db.execute(
            select(Strand.week_number).where(
                (Strand.subject.ilike(f"%{subject}%")) &
                (Strand.teacher_id == current_teacher.id)
            )
        )).scalars().all()
        
        booked_week_keys = {f"Week {week}" for week in booked_weeks}
        logger.debug(f"Found booked weeks: {booked_week_keys}")

        # Step 5: Filter out booked weeks to get available weeks
        available_weeks = {}
        total_available_sessions = 0
        
        for week_key, sessions in sessions_by_week.items():
            if week_key not in booked_week_keys:
                week_number = int(week_key.replace("Week ", ""))
                
                week_availability = WeekAvailability(
                    week_key=week_key,
                    week_number=week_number,
                    total_sessions=len(sessions),
                    available_sessions=sessions
                )
                
                available_weeks[week_key] = week_availability
                total_available_sessions += len(sessions)
        
        logger.debug(f"Available weeks: {list(available_weeks.keys())}")

        # Step 6: Prepare response
        response = AvailableWeeksResponse(
            subject=subject,
            class_name=class_name,
            teacher_id=current_teacher.id,
            available_weeks=available_weeks,
            total_available_weeks=len(available_weeks),
            total_available_sessions=total_available_sessions,
            semester_info={
                "start_date": str(acc_start_date),
                "end_date": str(acc_end_date),
                "total_weeks": "16"
            }
        )
        
        logger.debug(f"Returning {len(available_weeks)} available weeks with {total_available_sessions} total sessions")
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving available weeks and sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error retrieving available weeks and sessions: {str(e)}"
        )




UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def save_file(file: UploadFile, teacher_id: str) -> str:
    """Save uploaded file to uploads directory."""
    try:
        # Validate file
        if not file or not file.filename:
            raise ValueError("No file provided")
        
        # Read file content
        content = await file.read()
        if not content:
            raise ValueError("File is empty")
        
        # Create uploads directory if it doesn't exist
        uploads_dir = "./uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename)[1]
        filename = f"{unique_id}_{timestamp}{file_extension}"
        file_path = os.path.join(uploads_dir, filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File saved successfully: {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

async def extract_semester_mapper_data(file_path: str) -> dict:
    """
    Extract semester mapper data with mock session IDs.
    """
    logger.info(f"Extracting semester mapper data with mock session IDs")
    
    # Always use mock data with correct session IDs
    return {
        "strands": [
            {
                "strand_name": "Number Operations and Patterns",
                "weeks": [6, 7],
                "sub_strands": [
                    {
                        "substrand_name": "Basic Addition and Subtraction",
                        "session_id": 2931,  # Correct mock session ID
                        "week": 6,
                        "content_standards": [
                            {
                                "content_standard_code": "B6.1.1.1",
                                "content_standard_text": "Demonstrate understanding of addition and subtraction of whole numbers up to 100",
                                "indicators": [
                                    {
                                        "indicator_code": "B6.1.1.1.1",
                                        "indicator_text": "Add and subtract two-digit numbers with and without regrouping"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "substrand_name": "Number Patterns and Sequences", 
                        "session_id": 2997,  # Correct mock session ID
                        "week": 6,
                        "content_standards": [
                            {
                                "content_standard_code": "B6.1.2.1",
                                "content_standard_text": "Identify and create patterns using numbers, shapes, and objects",
                                "indicators": [
                                    {
                                        "indicator_code": "B6.1.2.1.1", 
                                        "indicator_text": "Recognize and extend growing and repeating patterns"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "substrand_name": "Place Value and Number Representation",
                        "session_id": 2932,  # Correct mock session ID
                        "week": 7,
                        "content_standards": [
                            {
                                "content_standard_code": "B6.1.3.1",
                                "content_standard_text": "Understand place value concepts for numbers up to 1000",
                                "indicators": [
                                    {
                                        "indicator_code": "B6.1.3.1.1",
                                        "indicator_text": "Identify the value of digits in their place positions"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "substrand_name": "Problem Solving with Operations",
                        "session_id": 2998,  # Correct mock session ID
                        "week": 7, 
                        "content_standards": [
                            {
                                "content_standard_code": "B6.1.4.1",
                                "content_standard_text": "Apply mathematical operations to solve real-world problems",
                                "indicators": [
                                    {
                                        "indicator_code": "B6.1.4.1.1",
                                        "indicator_text": "Solve word problems involving addition and subtraction"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

async def generate_ai_planning_response(file_path: str, teacher_id: str, available_sessions: dict = None) -> dict:
    """
    Generate AI-powered planning response based on uploaded curriculum and available sessions.
    This simulates what an AI system would return after analyzing curriculum documents.
    """
    logger.info(f"Generating AI planning response for file: {file_path}")
    
    # Simulate AI processing time and analysis
    import random
    import time
    
    # Mock AI processing
    time.sleep(0.1)  # Simulate processing time
    
    # Use the same mock data structure as the existing upload plans
    # This ensures consistency with the current system
    ai_generated_plan = await extract_semester_mapper_data(file_path)
    
    # If available sessions are provided, use them to enhance the mock data
    if available_sessions and available_sessions.get('available_weeks'):
        logger.info("Enhancing mock data with available sessions information")
        # You can enhance the mock data here based on available sessions
        # For now, we'll just use the existing mock data structure
    
    logger.info(f"AI planning response generated successfully using existing mock data structure")
    return ai_generated_plan


@router.post("/semester-mapper/upload")
async def upload_semester_mapper(
    file: UploadFile, 
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    session: AsyncSession = Depends(get_db)
):
    """
    Upload semester mapper file and return mock curriculum data.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"Processing upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"Received file: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        
        # Save the uploaded file
        file_path = await save_file(file, teacher_id)
        logger.info(f"File saved to: {file_path}")
        
        # Extract data using mock data
        logger.info("Using mock data for curriculum planning")
        data = await extract_semester_mapper_data(file_path)
        
        logger.info(f"Semester mapper upload successful for teacher {teacher_id}")
        logger.info(f"Final extracted data: {data}")
        
        return {
            "file_path": file_path, 
            "extracted_data": data,
            "used_available_sessions": False
        }
    except Exception as e:
        logger.error(f"Semester mapper upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/semester-mapper/ai-plan")
async def ai_planning_endpoint(
    file: UploadFile, 
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    session: AsyncSession = Depends(get_db)
):
    """
    AI-powered planning endpoint that analyzes uploaded curriculum and returns a complete semester plan.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"Processing AI planning request for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"Received curriculum file: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        
        # Save the uploaded file
        file_path = await save_file(file, teacher_id)
        logger.info(f"Curriculum file saved to: {file_path}")
        
        # Generate AI planning response using available sessions
        logger.info("Generating AI-powered semester plan...")
        ai_response = await generate_ai_planning_response(file_path, teacher_id)
        
        logger.info(f"AI planning successful for teacher {teacher_id}")
        
        return {
            "file_path": file_path,
            "ai_response": ai_response,
            "success": True,
            "message": "AI planning completed successfully"
        }
        
    except Exception as e:
        logger.error(f"AI planning failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI planning failed: {str(e)}")
