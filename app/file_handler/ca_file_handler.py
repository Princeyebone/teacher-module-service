from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4, UUID
import os
from app.core.logger import logger
from app.models.model import TeacherProfile, UploadedFile, AcademicCalendar, CalendarEvent, KnowledgeMetadata
from app.core.database import get_db
from datetime import datetime
from typing import Annotated, Optional
from app.core.dependencies import get_current_teacher
from app.core.config import settings
from app.services.gcs_utils import generate_signed_url, generate_file_name

router = APIRouter(tags=["Calendar File Handler"])


UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
    file_name: str = Form(...),  # Change from UploadFile to file_name string
    file_size: int = Form(...),  # Add file_size parameter
    file_type: str = Form(...),  # Add file_type parameter
    academic_year: Optional[str] = Form(None),
    institution_type: Optional[str] = Form(None),
    semester_type: Optional[str] = Form(None),
    current_semester: Optional[str] = Form(None),
    has_multiple_cohorts: Optional[bool] = Form(None),
    cohort_levels: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_db)
):
    """
    Upload calendar file endpoint.
    Accepts metadata only, generates signed URL for GCS, and returns the signed URL to the frontend.
    Teacher ID is extracted from the access token.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing calendar upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received metadata for file: {file_name}, size: {file_size}, content_type: {file_type}")
        
        # Log advanced settings
        logger.info(f"⚙️ Advanced settings: academic_year={academic_year}, institution_type={institution_type}, semester_type={semester_type}, current_semester={current_semester}, has_multiple_cohorts={has_multiple_cohorts}, cohort_levels={cohort_levels}")
        
        # Validate file type
        if not file_name:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        supported_types = ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'docx', 'xlsx', 'xls', 'txt']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_types)}"
            )
        
        # Generate file name for GCS
        gcs_file_name = generate_file_name(teacher_id, file_ext, "academic_calendar")
        logger.info(f"📂 Generated GCS file name: {gcs_file_name}")
        
        # Use the content_type from the uploaded file or default to application/octet-stream
        content_type = file_type if file_type else "application/octet-stream"
        logger.info(f"🏷️ File content type: {content_type}")
        
        # Generate signed URL for frontend to upload to GCS with correct content type
        # For file uploads, we need to use PUT method
        # Increase expiration time to 24 hours (86400 seconds) to prevent expiration issues
        signed_url = generate_signed_url(
            settings.GCS_BUCKET_NAME, 
            gcs_file_name, 
            method="PUT",
            content_type=content_type,
            expiration=86400  # 24 hours
        )
        logger.info(f"🔗 Generated signed URL for GCS upload")
        
        # Create a record in database
        uploaded_file = UploadedFile(
            teacher_id=UUID(teacher_id),
            file_name=file_name,
            file_type=file_ext,
            purpose="calendar",
            gcs_path=gcs_file_name,  # Store the GCS path
            extracted_text=None
        )
        
        session.add(uploaded_file)
        await session.commit()
        await session.refresh(uploaded_file)
        
        # Create KnowledgeMetadata record for RAG processing
        knowledge_record = KnowledgeMetadata(
            teacher_id=UUID(teacher_id),
            uploader_type="teacher",
            subject="Academic Calendar",
            level="General",
            region="",  # Could be added as a form parameter if needed
            pillar="curriculum",
            file_path=f"gs://{settings.GCS_BUCKET_NAME}/{gcs_file_name}",
            source_url=None,
            is_embedded=False,  # Will be processed by scheduler
            embedding_model=None,
            chunk_count=0,
            last_indexed_at=None,
            notes=f"Academic Calendar: {file_name}",
            checksum=None
        )
        
        session.add(knowledge_record)
        await session.commit()
        await session.refresh(knowledge_record)
        
        logger.info(f"✅ KnowledgeMetadata record created with ID: {knowledge_record.id}")
        
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
            "status": "success",
            "message": "Signed URL generated successfully. Use it to upload file to GCS.", 
            "signed_url": signed_url,
            "gcs_file_name": gcs_file_name,
            "content_type": content_type,  # Return content type so frontend can use it
            "teacher_id": teacher_id,
            "advanced_settings": advanced_settings,
            "knowledge_id": str(knowledge_record.id),
            "note": "Use the signed_url to upload your file to Google Cloud Storage directly. RAG processing will begin automatically in 120 seconds."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Calendar upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")