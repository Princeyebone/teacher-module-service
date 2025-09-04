from fastapi import APIRouter, UploadFile, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4, UUID
import os
from logger import logger
from model import WeeklyTimeTable
from database import get_db
from datetime import datetime
from typing import Annotated
from dependencies import get_current_teacher
from model import TeacherProfile
from enque_task import enqueue_timetable_processing  # Import the new background task function

router = APIRouter(tags=["File Handler"])


UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_file(file: UploadFile, teacher_id: str) -> str:
    """Save uploaded file with teacher_id + 'timetable' naming convention"""
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "unknown"
    # Use teacher_id + timetable naming as requested
    file_path = f"{UPLOAD_DIR}/{teacher_id}timetable.{file_ext}"
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    logger.info(f"File saved as: {file_path}")
    return file_path

# Note: extract_timetable_data function removed - now handled by background task in table_back.py


@router.post("/timetable/upload")
async def upload_timetable(current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], file: UploadFile, session: AsyncSession = Depends(get_db)):
    """
    Upload timetable file and enqueue background processing.
    Teacher ID is extracted from the access token.
    Processing will be done asynchronously with real-time updates via WebSocket.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"Processing timetable upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"Received file: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
        supported_types = ['pdf', 'jpg', 'jpeg', 'png', 'bmp', 'tiff', 'docx', 'xlsx', 'xls']
        
        if file_ext not in supported_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_types)}"
            )
        
        # Save the uploaded file
        file_path = await save_file(file, teacher_id)
        logger.info(f"File saved to: {file_path}")
        
        # Enqueue background processing task
        job_id = await enqueue_timetable_processing(teacher_id, file_path)
        
        if not job_id:
            raise HTTPException(status_code=500, detail="Failed to enqueue processing task")
        
        logger.info(f"Timetable processing job queued for teacher {teacher_id}: {job_id}")
        
        return {
            "status": "processing",
            "message": "File uploaded successfully. Processing in background...", 
            "job_id": job_id,
            "file_path": file_path,
            "teacher_id": teacher_id,
            "note": "Connect to WebSocket for real-time updates"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timetable upload failed: {e}")
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