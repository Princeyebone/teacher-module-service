from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.model import KnowledgeMetadata
from uuid import UUID, uuid4
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import os
from google.cloud import storage
from app.core.config import settings
from app.core.logger import logger

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Management"])

# Pydantic model for input data
class KnowledgeMetadataCreate(BaseModel):
    teacher_id: Optional[UUID] = None
    uploader_type: Optional[str] = "system"
    subject: Optional[str] = None
    level: Optional[str] = None
    region: Optional[str] = None
    pillar: Optional[str] = None
    file_path: Optional[str] = None
    source_url: Optional[str] = None
    license: Optional[str] = None
    is_embedded: bool = False
    embedding_model: Optional[str] = None
    chunk_count: Optional[int] = None
    last_indexed_at: Optional[datetime] = None
    notes: Optional[str] = None
    checksum: Optional[str] = None

@router.post("/input", summary="Insert knowledge metadata", status_code=status.HTTP_201_CREATED)
async def insert_knowledge_metadata(
    data: KnowledgeMetadataCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Handle timezone-aware datetime by converting to naive datetime if needed
        last_indexed_at = data.last_indexed_at
        if last_indexed_at and last_indexed_at.tzinfo is not None:
            # Convert to naive datetime by removing timezone info
            last_indexed_at = last_indexed_at.replace(tzinfo=None)
        
        # Create the knowledge metadata record
        knowledge_record = KnowledgeMetadata(
            teacher_id=data.teacher_id,
            uploader_type=data.uploader_type,
            subject=data.subject,
            level=data.level,
            region=data.region,
            pillar=data.pillar,
            file_path=data.file_path,
            source_url=data.source_url,
            license=data.license,
            is_embedded=data.is_embedded,
            embedding_model=data.embedding_model,
            chunk_count=data.chunk_count,
            last_indexed_at=last_indexed_at,
            notes=data.notes,
            checksum=data.checksum
        )
        
        # Add to database
        db.add(knowledge_record)
        await db.commit()
        await db.refresh(knowledge_record)
        
        return {"message": "Knowledge metadata inserted successfully", "id": knowledge_record.id}
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not insert knowledge metadata: {str(e)}"
        )

@router.post("/upload", summary="Create knowledge metadata record", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_file(
    note: str = Form(...),
    subject: str = Form(...),
    file_path: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Log the received data for debugging
        logger.info(f"Received note: {note}, subject: {subject}, file_path: {file_path}")
        
        # Create the knowledge metadata record with the specified values
        knowledge_record = KnowledgeMetadata(
            teacher_id=None,  # Should be null as requested
            uploader_type="system",  # Should be system
            subject=subject.strip(),  # The subject for this record
            level="all levels",  # Should be all levels
            region="all regions",  # Should be all regions
            pillar="Evaluation",  # Should be cognitive science and pedagogy
            file_path=file_path.strip() if file_path else None,  # The file path for this record
            source_url=None,  # Set source_url to null as requested
            license=None,  # Should be null
            is_embedded=False,  # Should be false
            embedding_model=None,
            chunk_count=0,  # Should be 0
            last_indexed_at=None,
            notes=note.strip(),  # The notes for this record
            checksum=None  # Should be null
        )
        
        # Add to database
        db.add(knowledge_record)
        await db.commit()
        await db.refresh(knowledge_record)
        
        return {
            "message": "Knowledge metadata created successfully",
            "id": knowledge_record.id
        }
    
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating knowledge metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create knowledge metadata: {str(e)}"
        )

def get_gcs_client():
    """Initialize and return GCS client"""
    try:
        if settings.GCS_SERVICE_ACCOUNT_JSON:
            # If service account JSON is provided as content
            if settings.GCS_SERVICE_ACCOUNT_JSON.startswith('{'):
                import json
                from google.oauth2 import service_account
                credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                client = storage.Client(credentials=credentials, project=settings.GCS_PROJECT_ID)
            # If service account JSON is provided as file path
            else:
                client = storage.Client.from_service_account_json(
                    settings.GCS_SERVICE_ACCOUNT_JSON, 
                    project=settings.GCS_PROJECT_ID
                )
        else:
            # Use default credentials (for development)
            client = storage.Client(project=settings.GCS_PROJECT_ID)
        return client
    except Exception as e:
        logger.error(f"❌ Failed to initialize GCS client: {e}")
        raise

@router.post("/upload-multiple", summary="Create knowledge metadata records", status_code=status.HTTP_201_CREATED)
async def upload_multiple_knowledge_files(
    notes: str = Form(...),  # Single string with notes separated by a delimiter
    subjects: str = Form(...),  # Single string with subjects separated by a delimiter
    file_paths: str = Form(None),  # Single string with file paths separated by a delimiter
    db: AsyncSession = Depends(get_db)
):
    try:
        # Split the notes and subjects by a delimiter (e.g., "|||")
        notes_list = notes.split("|||") if notes else []
        subjects_list = subjects.split("|||") if subjects else []
        file_paths_list = file_paths.split("|||") if file_paths else [None] * len(notes_list)
        
        # Log the received data for debugging
        logger.info(f"Received {len(notes_list)} notes, {len(subjects_list)} subjects")
        logger.info(f"Notes: {notes_list}")
        logger.info(f"Subjects: {subjects_list}")
        logger.info(f"File paths: {file_paths_list}")
        
        # Validate input lengths
        if len(notes_list) != len(subjects_list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Number of notes ({len(notes_list)}) and subjects ({len(subjects_list)}) must be equal"
            )
            
        # If file_paths is provided, it must match the length of notes/subjects
        if file_paths and len(file_paths_list) != len(notes_list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Number of file paths ({len(file_paths_list)}) must match number of notes ({len(notes_list)})"
            )
        
        if len(notes_list) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 10 records allowed"
            )
        
        if len(notes_list) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one note and subject must be provided"
            )
        
        # Process each note and subject pair
        results = []
        for i, (note, subject, file_path) in enumerate(zip(notes_list, subjects_list, file_paths_list)):
            # Create the knowledge metadata record with the specified values
            knowledge_record = KnowledgeMetadata(
                teacher_id=None,  # Should be null as requested
                uploader_type="system",  # Should be system
                subject=subject.strip(),  # The subject for this record
                level="all levels",  # Should be all levels
                region="all regions",  # Should be all regions
                pillar="Subject Specific Knowledge",  # Should be cognitive science and pedagogy
                file_path=file_path.strip() if file_path else None,  # The file path for this record
                source_url=None,  # Set source_url to null as requested
                license=None,  # Should be null
                is_embedded=False,  # Should be false
                embedding_model=None,
                chunk_count=0,  # Should be 0
                last_indexed_at=None,
                notes=note.strip(),  # The notes for this record
                checksum=None  # Should be null
            )
            
            # Add to database
            db.add(knowledge_record)
            await db.commit()
            await db.refresh(knowledge_record)
            
            results.append({
                "id": knowledge_record.id,
                "index": i,
                "message": "Knowledge metadata created successfully"
            })
        
        return {
            "message": f"Successfully created {len(results)} knowledge metadata records",
            "results": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating knowledge metadata: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create knowledge metadata: {str(e)}"
        )