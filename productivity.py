from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from model import AcademicCalendar, TeacherProfile, ClassSession, WeeklyTimeTable
from background import generate_schedule_task
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from celery.result import AsyncResult


router = APIRouter(tags=["Productivity"])

# utils.py or a helper module
def trigger_schedule_generation(teacher_id: str, country: str):
    result = generate_schedule_task.delay(teacher_id, country)
    return result.id

@router.post("/generate-schedule")
async def generate_schedule(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        teacher = (await db.execute(
            select(TeacherProfile).where(TeacherProfile.id == current_teacher.id)
        )).scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
        
        task_id = trigger_schedule_generation(str(teacher.id), teacher.country)
        return {
            "status": "processing",
            "message": f"Schedule generation started for teacher {teacher.id}.",
            "task_id": task_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/confirm-and-generate-schedule")
async def confirm_and_generate_schedule(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        existing_sessions = (await db.execute(
            select(ClassSession).where(ClassSession.teacher_id == current_teacher.id)
        )).scalars().all()

        if existing_sessions:
            return {
                "status": "exists",
                "message": f"{len(existing_sessions)} class sessions already exist for teacher {current_teacher.id}."
            }
        
        timetable = (await db.execute(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )).scalars().all()
        academic = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalars().all()

        if not timetable or not academic:
            return {
                "status": "error",
                "message": "No timetable or academic calendar found, please create one first"
            }

        task_id = trigger_schedule_generation(str(current_teacher.id), current_teacher.country)
        return {
            "status": "processing",
            "message": f"No existing schedule found. Started generation for teacher {current_teacher.id}.",
            "task_id": task_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task-status/{task_id}")
def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    return {"task_id": task_id, "status": result.status}