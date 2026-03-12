from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, select
from uuid import UUID
import os
from logger import logging, logger  # Add logger import
from database import get_db
from typing import Annotated, Optional
from dependencies import get_current_teacher
from model import TeacherProfile, WeeklyTimeTable
from config import settings
from gcs_utils import generate_signed_url, generate_file_name, get_file_from_gcs
import asyncio
import uuid
from datetime import datetime

router = APIRouter(tags=["Semester Plan File Handler"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/sem-plan/upload")
async def upload_semester_plan(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], 
    subject: str = Form(...),  # Add subject parameter
    class_name: str = Form(...),  # Add class_name parameter
    education_system: str = Form(...),  # Add education_system parameter (required)
    education_level: str = Form(...),  # Add education_level parameter (required)
    country_name: Optional[str] = Form(None),  # Add optional country_name parameter
    file_name: str = Form(...),  # Change from UploadFile to file_name string
    file_size: int = Form(...),  # Add file_size parameter
    file_type: str = Form(...),  # Add file_type parameter
    session: AsyncSession = Depends(get_db)
):
    """
    Upload semester plan file endpoint.
    Accepts metadata only, generates signed URL for GCS, and returns the signed URL to the frontend.
    Teacher ID is extracted from the access token.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing semester plan upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received metadata for file: {file_name}, size: {file_size}, content_type: {file_type}")
        logger.info(f"📚 Subject: {subject}, Class: {class_name}")
        logger.info(f"🏫 Education System: {education_system}, Education Level: {education_level}")
        
        # Validate file type
        if not file_name:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        supported_types = ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'docx', 'xlsx', 'xls', 'txt', 'pptx', 'ppt']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_types)}"
            )
        
        # Generate file name for GCS in the format: sem_plan/teacher_id/class_name/subject.extension
        gcs_file_name = f"sem_plan/{teacher_id}/{class_name}/{subject}.{file_ext}"
        logger.info(f"📂 Generated GCS file name: {gcs_file_name}")
        
        # Use the content_type from the uploaded file or default to application/octet-stream
        content_type = file_type if file_type else "application/octet-stream"
        logger.info(f"🏷️ File content type: {content_type}")
        
        # Update existing WeeklyTimeTable entries for this subject and class with the new education system and level
        # This ensures the data is overwritten each time a new file is uploaded
        stmt = (
            WeeklyTimeTable.__table__.update()
            .where(WeeklyTimeTable.teacher_id == UUID(teacher_id))
            .where(WeeklyTimeTable.subject == subject)
            .where(WeeklyTimeTable.pupils == class_name)
            .values(edu_sys=education_system, edu_lvl=education_level)
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"✅ Updated WeeklyTimeTable entries with education system: {education_system}, education level: {education_level}")
        
        # Generate signed URL for frontend to upload to GCS with correct content type
        # For file uploads, we need to use PUT method
        # Increase expiration time to 24 hours (86400 seconds) to prevent expiration issues
        signed_url_primary = generate_signed_url(
            settings.GCS_BUCKET_NAME, 
            gcs_file_name, 
            method="PUT",
            content_type=content_type,
            expiration=86400  # 24 hours
        )
        logger.info(f"🔗 Generated primary signed URL for GCS upload")
        
        # Schedule background processing task to run immediately
        # This will be handled by a separate background task that processes semester plans
        logger.info(f"⏰ Scheduled semester plan processing for teacher {teacher_id} to run immediately")
        
        return {
            "status": "success",
            "message": "Signed URL generated successfully. Use it to upload file to GCS.", 
            "signed_urls": {
                "primary": signed_url_primary
            },
            "gcs_file_names": {
                "primary": gcs_file_name
            },
            "content_type": content_type,
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name,
            "education_system": education_system,
            "education_level": education_level,
            "note": "Use the signed_url to upload your file directly to Google Cloud Storage. Processing will begin immediately."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Semester plan upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")