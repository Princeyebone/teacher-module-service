from fastapi import APIRouter, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from uuid import uuid4, UUID
import os
from app.core.logger import logger
from app.models.model import KnowledgeMetadata
from app.core.database import get_db
from datetime import datetime
from typing import Annotated, Optional
from app.core.dependencies import get_current_teacher
from app.models.model import TeacherProfile
from app.core.config import settings
from app.services.gcs_utils import generate_signed_url, generate_file_name
import json

router = APIRouter(tags=["RAG File Handler"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/rag/upload")
async def upload_rag_file(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], 
    file_name: str = Form(...),  # Change from UploadFile to file_name string
    file_size: int = Form(...),  # Add file_size parameter
    file_type: str = Form(...),  # Add file_type parameter
    subject: str = Form(...),
    notes: Optional[str] = Form(None),
    level: str = Form(...),
    region: str = Form(...),
    source_url: Optional[str] = Form(None),
    file_path_field: Optional[str] = Form(None),
    pillar: str = Form(...),
    session: AsyncSession = Depends(get_db)
):
    """
    Upload RAG file for processing.
    Accepts metadata only, generates signed URL for GCS, and returns the signed URL to the frontend.
    
    Args:
        current_teacher: Current teacher profile from authentication
        file_name: Name of the file to upload
        file_size: Size of the file in bytes
        file_type: MIME type of the file
        subject: Subject of the document
        notes: Optional notes about the document
        level: Educational level (e.g., "High School", "University")
        region: Geographic region (e.g., "Ghana", "Kenya")
        source_url: Optional URL where the document was sourced
        file_path_field: Optional file path in storage
        pillar: Knowledge pillar (e.g., "curriculum", "cognitive", "assessment", "pedagogy")
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"🚀 Processing RAG upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"📁 Received metadata for file: {file_name}, size: {file_size}, content_type: {file_type}")
        
        # Validate file type
        if not file_name:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        # Only accept PDF files
        supported_types = ['pdf']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Only PDF files are supported for RAG processing."
            )
        
        # Generate file name for GCS using the new folder structure based on pillar with original filename
        gcs_file_name = generate_file_name(teacher_id, file_ext, "rag", pillar, file_name)
        logger.info(f"📂 Generated GCS file name: {gcs_file_name}")
        
        # Enhanced duplication detection
        # Search for files with the same filename in their path, same teacher_id, and same subject
        filename_without_ext = os.path.splitext(file_name)[0] if file_name else ""
        if filename_without_ext:
            from sqlalchemy import or_, func
            
            # Search for existing records where:
            # 1. Teacher ID matches
            # 2. Subject matches
            # 3. Filename is found in the file_path (using ILIKE for case-insensitive search)
            result = await session.execute(
                select(KnowledgeMetadata).where(
                    and_(
                        KnowledgeMetadata.teacher_id == UUID(teacher_id),
                        KnowledgeMetadata.subject == subject,
                        or_(
                            KnowledgeMetadata.file_path.ilike(f"%{filename_without_ext}%"),
                            KnowledgeMetadata.notes == filename_without_ext,
                            KnowledgeMetadata.notes.ilike(f"{filename_without_ext} (%")
                        )
                    )
                )
            )
            existing_records = result.scalars().all()
            
            # Check if any existing records match our criteria
            duplicate_found = False
            existing_record = None
            
            for record in existing_records:
                # If we find a record that's already embedded, it's a duplicate
                if record.is_embedded:
                    duplicate_found = True
                    existing_record = record
                    break
                # If we find a record that's not embedded, we can update it
                elif not existing_record:
                    existing_record = record
            
            if duplicate_found:
                # File already exists and is embedded, notify user
                from app.sch_ground.background import publish_ws_message
                await publish_ws_message(teacher_id, {
                    "status": "duplicate",
                    "message": f"File {file_name} already exists and has been processed.",
                    "file_name": file_name,
                    "task_type": "rag_processing"
                })
                
                return {
                    "status": "duplicate",
                    "message": f"File {file_name} already exists and has been processed.",
                    "knowledge_id": str(existing_record.id)
                }
            elif existing_record:
                # File exists but not embedded, update the existing record
                knowledge_id = existing_record.id
                logger.info(f"🔁 Updating existing KnowledgeMetadata record: {knowledge_id}")
                
                # Update the existing record with new metadata
                existing_record.subject = subject
                existing_record.level = level
                existing_record.region = region
                existing_record.pillar = pillar
                existing_record.file_path = file_path_field or f"gs://teacher_module_acatable_bucket/{gcs_file_name}"
                existing_record.source_url = source_url
                existing_record.is_embedded = False
                existing_record.embedding_model = None
                existing_record.chunk_count = 0
                existing_record.last_indexed_at = None
                existing_record.notes = f"{filename_without_ext} ({notes})" if notes else filename_without_ext
                existing_record.checksum = None
                
                await session.commit()
                await session.refresh(existing_record)
            else:
                # File doesn't exist, create new record
                logger.info("🆕 Creating new KnowledgeMetadata record")
                
                # Create initial KnowledgeMetadata record
                knowledge_record = KnowledgeMetadata(
                    teacher_id=UUID(teacher_id),
                    uploader_type="teacher",
                    subject=subject,
                    level=level,
                    region=region,
                    pillar=pillar,
                    file_path=file_path_field or f"gs://teacher_module_acatable_bucket/{gcs_file_name}",
                    source_url=source_url,
                    is_embedded=False,
                    embedding_model=None,
                    chunk_count=0,
                    last_indexed_at=None,
                    notes=f"{filename_without_ext} ({notes})" if notes else filename_without_ext,
                    checksum=None
                )
                
                session.add(knowledge_record)
                await session.commit()
                await session.refresh(knowledge_record)
                
                knowledge_id = knowledge_record.id
                logger.info(f"✅ KnowledgeMetadata record created with ID: {knowledge_id}")
        else:
            # No filename, create new record without duplication check
            logger.info("🆕 Creating new KnowledgeMetadata record (no filename)")
            
            # Create initial KnowledgeMetadata record
            knowledge_record = KnowledgeMetadata(
                teacher_id=UUID(teacher_id),
                uploader_type="teacher",
                subject=subject,
                level=level,
                region=region,
                pillar=pillar,
                file_path=file_path_field or f"gs://teacher_module_acatable_bucket/{gcs_file_name}",
                source_url=source_url,
                is_embedded=False,
                embedding_model=None,
                chunk_count=0,
                last_indexed_at=None,
                notes=notes or "",
                checksum=None
            )
            
            session.add(knowledge_record)
            await session.commit()
            await session.refresh(knowledge_record)
            
            knowledge_id = knowledge_record.id
            logger.info(f"✅ KnowledgeMetadata record created with ID: {knowledge_id}")
        
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
        
        # Prepare metadata for the background task
        # For existing records, knowledge_id is already set
        # For new records without filename, we need to get the knowledge_id
        if 'knowledge_id' not in locals():
            knowledge_id = knowledge_record.id
        
        metadata = {
            "subject": subject,
            "notes": f"{os.path.splitext(file_name)[0]} ({notes})" if notes else os.path.splitext(file_name)[0] if file_name else "",
            "level": level,
            "region": region,
            "source_url": source_url,
            "file_path": file_path_field or f"gs://teacher_module_acatable_bucket/{gcs_file_name}",
            "pillar": pillar
        }
        
        return {
            "status": "success",
            "message": "Signed URL generated successfully. Use it to upload file to GCS.", 
            "signed_url": signed_url,
            "gcs_file_name": gcs_file_name,
            "content_type": content_type,
            "teacher_id": teacher_id,
            "knowledge_id": str(knowledge_id),
            "metadata": metadata,
            "note": "Use the signed_url to upload your file directly to Google Cloud Storage. RAG processing will begin automatically after upload."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 RAG upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")