from fastapi import APIRouter, UploadFile, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
import os
from logger import logger
from model import TeacherProfile
from database import get_db
from typing import Annotated
from dependencies import get_current_teacher

router = APIRouter(tags=["Calendar File Handler"])


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

async def extract_calendar_data(file_path: str) -> dict:
    return {
        "academic_calendar": {
            "semester_name": "2nd Semester",
            "academic_level": "Level 200",
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
async def upload_calendar(current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)], file: UploadFile, session: AsyncSession = Depends(get_db)):
    """
    Upload calendar file and return extracted data.
    Teacher ID is extracted from the access token.
    """
    try:
        teacher_id = str(current_teacher.id)
        logger.info(f"Processing calendar upload for teacher: {teacher_id}")
        
        # Log file details
        logger.info(f"Received file: {file.filename}, size: {file.size}, content_type: {file.content_type}")
        
        # Save the uploaded file
        file_path = await save_file(file, teacher_id)
        logger.info(f"File saved to: {file_path}")
        
        # Extract calendar data
        data = await extract_calendar_data(file_path)
        logger.info(f"Calendar upload successful for teacher {teacher_id}")
        
        return {"file_path": file_path, "extracted_data": data}
    except Exception as e:
        logger.error(f"Calendar upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

