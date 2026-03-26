from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from app.models.model import AcademicCalendar, TeacherProfile, ClassSession, WeeklyTimeTable
from app.core.dependencies import get_current_teacher
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


router = APIRouter(tags=["Productivity"])

# This endpoint can be kept for manual triggering if needed
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
        
        # Check if both timetable and academic calendar exist
        timetable_exists = (await db.execute(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)
        )).scalars().first() is not None
        
        academic_calendar_exists = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none() is not None
        
        if not timetable_exists:
            raise HTTPException(status_code=400, detail="No timetable found. Please create a timetable first.")
            
        if not academic_calendar_exists:
            raise HTTPException(status_code=400, detail="No academic calendar found. Please create an academic calendar first.")
        
        # For manual triggering, we can return a message indicating that
        # the automatic trigger should have already handled this
        return {
            "status": "info",
            "message": "Session generation is automatically triggered when both timetable and academic calendar are saved. No manual action needed."
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

        # For manual confirmation, we can return a message indicating that
        # the automatic trigger should have already handled this
        return {
            "status": "info",
            "message": "Session generation is automatically triggered when both timetable and academic calendar are saved. No manual action needed."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task-status/{job_id}")
async def get_task_status(job_id: str):
    """This endpoint can be removed if not needed, as the automatic trigger doesn't return job IDs"""
    return {
        "job_id": job_id,
        "status": "deprecated",
        "message": "Session generation is now automatically triggered. This endpoint is deprecated."
    }