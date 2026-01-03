from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4, UUID
import os
from logger import logger
from model import CurriculumPlan
from database import get_db
from datetime import datetime
from typing import Annotated, Optional
from dependencies import get_current_teacher
from model import TeacherProfile
from config import settings
from gcs_utils import generate_signed_url, generate_file_name

router = APIRouter(tags=["Curriculum Plan Handler"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/curriculum-plan/upload")
async def upload_curriculum_plan(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], 
    file_name: str = Form(...),  # Change from UploadFile to file_name string
    file_size: int = Form(...),  # Add file_size parameter
    file_type: str = Form(...),  # Add file_type parameter
    subject: str = Form(...),
    grade_level: str = Form(...),
    term: str = Form(...),
    week: str = Form(...),
    topic: str = Form(...),
    sub_topic: str = Form(...),
    duration: str = Form(...),
    class_activities: str = Form(...),
    session: AsyncSession = Depends(get_db)
):
    """
    Upload curriculum plan file.
    Accepts metadata only, generates signed URL for GCS, and returns the signed URL to the frontend.
    
    Args:
        current_teacher: Current teacher profile from authentication
        file_name: Name of the file to upload
        file_size: Size of the file in bytes
        file_type: MIME type of the file
        subject: Subject of the curriculum plan
        grade_level: Grade level (e.g., "Grade 10")
        term: Term (e.g., "Term 1")
        week: Week number
        topic: Main topic
        sub_topic: Sub-topic
        duration: Duration of the lesson
        class_activities: Description of class activities
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing curriculum plan upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received metadata for file: {file_name}, size: {file_size}, content_type: {file_type}")
        
        # Validate file type
        if not file_name:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        supported_types = ['pdf', 'docx', 'xlsx', 'xls']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_types)}"
            )
        
        # Generate file name for GCS
        gcs_file_name = generate_file_name(teacher_id, file_ext, "curriculum_plans")
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
        
        # Create initial CurriculumPlan record
        curriculum_plan = CurriculumPlan(
            teacher_id=UUID(teacher_id),
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            subject=subject,
            grade_level=grade_level,
            term=term,
            week=week,
            topic=topic,
            sub_topic=sub_topic,
            duration=duration,
            class_activities=class_activities,
            gcs_path=gcs_file_name,
            extracted_text=""  # Will be populated by background task
        )
        
        session.add(curriculum_plan)
        await session.commit()
        await session.refresh(curriculum_plan)
        
        logger.info(f"✅ Curriculum plan record created with ID: {curriculum_plan.id}")
        
        # Create KnowledgeMetadata record for RAG processing
        from model import KnowledgeMetadata
        
        # Create KnowledgeMetadata record
        knowledge_record = KnowledgeMetadata(
            teacher_id=UUID(teacher_id),
            uploader_type="teacher",
            subject=subject,
            level=grade_level,
            region="",  # Could be added as a form parameter if needed
            pillar="curriculum",
            file_path=f"gs://{settings.GCS_BUCKET_NAME}/{gcs_file_name}",
            source_url=None,
            is_embedded=False,  # Will be processed by scheduler
            embedding_model=None,
            chunk_count=0,
            last_indexed_at=None,
            notes=f"Curriculum Plan: {topic} - {sub_topic}",
            checksum=None
        )
        
        session.add(knowledge_record)
        await session.commit()
        await session.refresh(knowledge_record)
        
        logger.info(f"✅ KnowledgeMetadata record created with ID: {knowledge_record.id}")
        
        return {
            "status": "success",
            "message": "Signed URL generated successfully. Use it to upload file to GCS.", 
            "signed_url": signed_url,
            "gcs_file_name": gcs_file_name,
            "content_type": content_type,
            "teacher_id": teacher_id,
            "knowledge_id": str(knowledge_record.id),
            "note": "Use the signed_url to upload your file directly to Google Cloud Storage. RAG processing will begin automatically after upload."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Curriculum plan upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")