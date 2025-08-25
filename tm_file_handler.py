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

router = APIRouter(tags=["File Handler"])


UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_file(file: UploadFile, teacher_id: str) -> str:
    file_id = str(uuid4())
    file_ext = file.filename.split(".")[-1]
    file_path = f"{UPLOAD_DIR}/{teacher_id}_{file_id}.{file_ext}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return file_path

async def extract_timetable_data(file_path: str) -> dict:
    return {
        "timetables": [
            {"weekday": "Monday", "start_time": "09:00", "end_time": "10:00", "subject": "Math", "pupils": "Class A"},
            {"weekday": "Wednesday", "start_time": "11:00", "end_time": "12:00", "subject": "Science", "pupils": "Class B"}
        ]
    }


@router.post("/timetable/upload")
async def upload_timetable(current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], file: UploadFile, session: AsyncSession = Depends(get_db)):
    """
    Upload timetable file and return extracted data.
    Teacher ID is extracted from the access token.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"Processing timetable upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"Received file: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        
        # Save the uploaded file
        file_path = await save_file(file, teacher_id)
        logger.info(f"File saved to: {file_path}")
        
        # Extract timetable data
        data = await extract_timetable_data(file_path)
        logger.info(f"Timetable upload successful for teacher {teacher_id}")
        
        return {"file_path": file_path, "extracted_data": data}
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