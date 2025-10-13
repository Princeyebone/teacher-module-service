from fastapi import APIRouter, UploadFile, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import os
from logger import logger
from database import get_db
from typing import Annotated
from dependencies import get_current_teacher
from model import TeacherProfile
from config import settings
from gcs_utils import generate_signed_url, generate_file_name, get_file_from_gcs
import asyncio
import uuid
from datetime import datetime
from semplan_ground.semplan_back import enqueue_semplan_processing  # Keep import for semester plan processing

router = APIRouter(tags=["Curriculum File Handler"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/curriculum/upload")
async def upload_curriculum(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], 
    subject: str = Form(...),  # Add subject parameter
    class_name: str = Form(...),  # Add class_name parameter
    file: UploadFile = Form(...), 
    session: AsyncSession = Depends(get_db)
):
    """
    Upload curriculum file endpoint.
    Renames the file to curriculum/teacher_id/class_name/subject.file_extension, generates a signed URL for GCS,
    and returns the signed URL to the frontend for direct upload to Google Cloud Storage.
    Teacher ID is extracted from the access token.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing curriculum upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received file: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        logger.info(f"📚 Subject: {subject}, Class: {class_name}")
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        supported_types = ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'docx', 'xlsx', 'xls', 'txt', 'pptx', 'ppt']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_types)}"
            )
        
        # Generate file name for GCS in the format: curriculum/teacher_id/class_name/subject.extension
        gcs_file_name = f"curriculum/{teacher_id}/{class_name}/{subject}.{file_ext}"
        logger.info(f"📂 Generated GCS file name: {gcs_file_name}")
        
        # Use the content_type from the uploaded file or default to application/octet-stream
        content_type = file.content_type if file.content_type else "application/octet-stream"
        logger.info(f"🏷️ File content type: {content_type}")
        
        # Generate signed URL for frontend to upload to GCS with correct content type
        # For file uploads, we need to use PUT method
        signed_url = generate_signed_url(
            settings.GCS_BUCKET_NAME, 
            gcs_file_name, 
            method="PUT",
            content_type=content_type
        )
        logger.info(f"🔗 Generated signed URL for GCS upload")
        
        return {
            "status": "success",
            "message": "Signed URL generated successfully. Use it to upload file to GCS.", 
            "signed_url": signed_url,
            "gcs_file_name": gcs_file_name,
            "content_type": content_type,
            "teacher_id": teacher_id,
            "subject": subject,
            "class_name": class_name,
            "note": "Use the signed_url to upload your file directly to Google Cloud Storage."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Curriculum upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

