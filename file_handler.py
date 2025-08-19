from fastapi import APIRouter, UploadFile, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4, UUID
import os
from logger import logger
from model import WeeklyTimeTable
from database import get_db
from datetime import datetime

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

@router.post("/timetable/upload/{teacher_id}")
async def upload_timetable(teacher_id: str, file: UploadFile, session: AsyncSession = Depends(get_db)):
    try:
        UUID(teacher_id)  # Validate teacher_id
        file_path = await save_file(file, teacher_id)
        data = await extract_timetable_data(file_path)
        return {"file_path": file_path, "extracted_data": data}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid teacher_id")
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

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