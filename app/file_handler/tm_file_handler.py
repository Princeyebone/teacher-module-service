from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4, UUID
import os
from app.core.logger import logger
from app.models.model import WeeklyTimeTable, UploadedFile, KnowledgeMetadata
from app.core.database import get_db
from datetime import datetime
from typing import Annotated
from app.core.dependencies import get_current_teacher
from app.models.model import TeacherProfile
from app.core.config import settings
from app.services.gcs_utils import generate_signed_url, generate_file_name

router = APIRouter(tags=["File Handler"])


UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/timetable/upload")
async def upload_timetable(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], 
    file_name: str = Form(...),  # Change from UploadFile to file_name string
    file_size: int = Form(...),  # Add file_size parameter
    file_type: str = Form(...),  # Add file_type parameter
    session: AsyncSession = Depends(get_db)
):
    """
    Upload timetable file endpoint.
    Accepts metadata only, generates signed URL for GCS, and returns the signed URL to the frontend.
    Teacher ID is extracted from the access token.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing timetable upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received metadata for file: {file_name}, size: {file_size}, content_type: {file_type}")
        
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
        gcs_file_name = generate_file_name(teacher_id, file_ext)
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
            purpose="timetable",
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
            subject="Timetable",
            level="General",
            region="",  # Could be added as a form parameter if needed
            pillar="curriculum",
            file_path=f"gs://{settings.GCS_BUCKET_NAME}/{gcs_file_name}",
            source_url=None,
            is_embedded=False,  # Will be processed by scheduler
            embedding_model=None,
            chunk_count=0,
            last_indexed_at=None,
            notes=f"Timetable: {file_name}",
            checksum=None
        )
        
        session.add(knowledge_record)
        await session.commit()
        await session.refresh(knowledge_record)
        
        logger.info(f"✅ KnowledgeMetadata record created with ID: {knowledge_record.id}")
        
        return {
            "status": "success",
            "message": "Signed URL generated successfully. Use it to upload file to GCS.", 
            "file_path": file_name,
            "file_id": str(uploaded_file.id),
            "signed_url": signed_url,
            "gcs_file_name": gcs_file_name,
            "content_type": content_type,  # Return content type so frontend can use it
            "teacher_id": teacher_id,
            "knowledge_id": str(knowledge_record.id),
            "note": "Use the signed_url to upload your file to Google Cloud Storage directly. RAG processing will begin automatically in 120 seconds."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 Timetable upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/timetable/confirm/{teacher_id}")
async def confirm_timetable(teacher_id: str, data: dict, session: AsyncSession = Depends(get_db)):
    try:
        UUID(teacher_id)  # Validate teacher_id
        if not data.get("timetables"):
            raise HTTPException(status_code=400, detail="No timetable data to save")
        for entry in data.get("timetables", []):
            timetable = WeeklyTimeTable(
                teacher_id=teacher_id,
                weekday=entry["weekday"],
                start_time=entry["start_time"],
                end_time=entry["end_time"],
                subject=entry["subject"],
                pupils=entry["pupils"],
                created_at=datetime.utcnow()
            )
            session.add(timetable)
        await session.commit()
        return {"status": "success", "message": f"Timetable saved for teacher {teacher_id}"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid teacher_id")
    except Exception as e:
        logger.error(f"Confirmation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to save timetable")