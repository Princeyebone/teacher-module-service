from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from model import AcademicCalendar, TeacherProfile, ClassSession, WeeklyTimeTable
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from enque_task import enqueue_schedule_generation, check_job_status


router = APIRouter(tags=["Productivity"])

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
        
        # Use ARQ to enqueue the task
        job_id = await enqueue_schedule_generation(str(teacher.id), teacher.country or "Ghana")
        
        if job_id:
            return {
                "status": "processing",
                "message": f"Schedule generation started for teacher {teacher.id}.",
                "job_id": job_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to queue schedule generation task")
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

        # Use ARQ to enqueue the task
        job_id = await enqueue_schedule_generation(str(current_teacher.id), current_teacher.country or "Ghana")
        
        if job_id:
            return {
                "status": "processing",
                "message": f"No existing schedule found. Started generation for teacher {current_teacher.id}.",
                "job_id": job_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to queue schedule generation task")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task-status/{job_id}")
async def get_task_status(job_id: str):
    """Check the status of an ARQ background job"""
    try:
        status = await check_job_status(job_id)
        return {
            "job_id": job_id,
            "status": status.get("status", "unknown"),
            "details": status
        }
    except Exception as e:
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(e)
        }