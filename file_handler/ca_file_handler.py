from fastapi import APIRouter, UploadFile, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4, UUID
import os
from logger import logger
from model import TeacherProfile, UploadedFile, AcademicCalendar, CalendarEvent
from database import get_db
from datetime import datetime
from typing import Annotated, Optional
from dependencies import get_current_teacher
from enque_task import enqueue_calendar_processing  # Import the new background task function
from config import settings
from gcs_utils import generate_signed_url, generate_file_name

router = APIRouter(tags=["Calendar File Handler"])


UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_file(file: UploadFile, teacher_id: str) -> str:
    """Save uploaded file with 'academic_calendar/teacher_id.extension' naming convention"""
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "unknown"
    # Use academic_calendar/teacher_id.extension naming as requested
    file_path = f"{UPLOAD_DIR}/academic_calendar/{teacher_id}.{file_ext}"
    
    # Create the academic_calendar directory if it doesn't exist
    academic_calendar_dir = os.path.dirname(file_path)
    os.makedirs(academic_calendar_dir, exist_ok=True)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    logger.info(f"💾 File saved as: {file_path}")
    return file_path

async def extract_calendar_data(file_path: str) -> dict:
    return {
        "academic_calendar": {
            "semester_name": "2nd Semester",
            "semester_start_date": "2024-08-15",
            "semester_end_date": "2024-12-20",
            "mid_semester_break_start_date": "2024-10-15",
            "mid_semester_break_end_date": "2024-10-22",
            "midsem_exams_date": "2024-10-08",
            "revision_start_date": "2024-12-01"
        },
        "calendar_events": [
            {
                "event_name": "Orientation Week",
                "event_start_date": "2024-08-12",
                "event_end_date": "2024-08-14",
                "event_start_time": "08:00",
                "event_end_time": "17:00",
                "is_holiday": False,
                "requires_no_classes": True
            },
            {
                "event_name": "Independence Day",
                "event_start_date": "2024-09-21",
                "event_end_date": "2024-09-21",
                "event_start_time": "",
                "event_end_time": "",
                "is_holiday": True,
                "requires_no_classes": True
            },
            {
                "event_name": "End of Semester Exams",
                "event_start_date": "2024-12-02",
                "event_end_date": "2024-12-13",
                "event_start_time": "08:00",
                "event_end_time": "16:00",
                "is_holiday": False,
                "requires_no_classes": True
            }
        ]
    }

@router.post("/calendar/upload")
async def upload_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], 
    file: UploadFile, 
    academic_year: Optional[str] = Form(None),
    institution_type: Optional[str] = Form(None),
    semester_type: Optional[str] = Form(None),
    current_semester: Optional[str] = Form(None),
    has_multiple_cohorts: Optional[bool] = Form(None),
    cohort_levels: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db)
):
    """
    Upload calendar file for text extraction.
    After processing, returns a signed URL for frontend to upload to Google Cloud Storage.
    Teacher ID is extracted from the access token.
    Processing will be done asynchronously with real-time updates via WebSocket.
    Accepts advanced settings from the frontend.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing calendar upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received file: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        
        # Log advanced settings
        logger.info(f"⚙️ Advanced settings: academic_year={academic_year}, institution_type={institution_type}, semester_type={semester_type}, current_semester={current_semester}, has_multiple_cohorts={has_multiple_cohorts}, cohort_levels={cohort_levels}")
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        supported_types = ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'docx', 'xlsx', 'xls', 'txt']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_types)}"
            )
        
        # Save the uploaded file locally
        file_path = await save_file(file, teacher_id)
        logger.info(f"✅ File saved locally to: {file_path}")
        
        # Generate file name for GCS
        gcs_file_name = generate_file_name(teacher_id, file_ext, "academic_calendar")
        logger.info(f"📂 Generated GCS file name: {gcs_file_name}")
        
        # Use the content_type from the uploaded file or default to application/octet-stream
        content_type = file.content_type if file.content_type else "application/octet-stream"
        logger.info(f"🏷️ File content type: {content_type}")
        
        # Generate signed URL for frontend to upload to GCS with correct content type
        signed_url = generate_signed_url(settings.GCS_BUCKET_NAME, gcs_file_name, content_type)
        logger.info(f"🔗 Generated signed URL for GCS upload")
        
        # Create a record in database
        uploaded_file = UploadedFile(
            teacher_id=UUID(teacher_id),
            file_name=file.filename,
            file_type=file_ext,
            purpose="calendar",
            gcs_path=gcs_file_name,  # Store the GCS path
            extracted_text=None
        )
        
        session.add(uploaded_file)
        await session.commit()
        await session.refresh(uploaded_file)
        
        # Prepare additional data for AI processing from the form fields
        additional_data_parts = []
        if academic_year:
            additional_data_parts.append(f"Academic Year: {academic_year}")
        if institution_type:
            additional_data_parts.append(f"Institution Type: {institution_type}")
        if semester_type:
            additional_data_parts.append(f"Semester Type: {semester_type}")
        if current_semester:
            additional_data_parts.append(f"Current Semester: {current_semester}")
        if has_multiple_cohorts is not None:
            additional_data_parts.append(f"Has Multiple Cohorts: {has_multiple_cohorts}")
        if cohort_levels:
            additional_data_parts.append(f"Cohort Levels: {cohort_levels}")
            
        additional_data = "\n".join(additional_data_parts)
        
        # Enqueue background processing task for text extraction
        job_id = await enqueue_calendar_processing(teacher_id, file_path, gcs_file_name, additional_data)
        
        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to enqueue processing task")
        
        logger.info(f"[JOB] Calendar processing job queued for teacher {teacher_id}: {job_id}")
        
        # Include advanced settings in the response for potential future use
        advanced_settings = {
            "academic_year": academic_year,
            "institution_type": institution_type,
            "semester_type": semester_type,
            "current_semester": current_semester,
            "has_multiple_cohorts": has_multiple_cohorts,
            "cohort_levels": cohort_levels
        }
        
        return {
            "status": "processing",
            "message": "File uploaded successfully. Processing in background...", 
            "job_id": job_id,
            "file_path": file_path,
            "file_id": str(uploaded_file.id),
            "signed_url": signed_url,
            "gcs_file_name": gcs_file_name,
            "content_type": content_type,  # Return content type so frontend can use it
            "teacher_id": teacher_id,
            "advanced_settings": advanced_settings,  # Include advanced settings in response
            "note": "Connect to WebSocket for real-time updates. Use signed_url to upload to GCS."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Calendar upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")