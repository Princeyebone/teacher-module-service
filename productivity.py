# productivty.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from model import AcademicCalendar, TeacherProfile, ClassSession, WeeklyTimeTable
from background import generate_schedule_task
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import Session, select
from celery.result import AsyncResult
from celery_app import celery_app

router=APIRouter(tags=["Productivity"])


# utils.py or a helper module
def trigger_schedule_generation(teacher_id: str, country: str):
    result = generate_schedule_task.delay(teacher_id, country)
    return result.id


@router.post("/generate-schedule")
async def generate_schedule(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    teacher = db.exec(select(TeacherProfile).where(TeacherProfile.id == current_teacher.id)).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    try:
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
    db: Session = Depends(get_db)
):
    existing_sessions = db.exec(
        select(ClassSession).where(ClassSession.teacher_id == current_teacher.id)
    ).all()

    if existing_sessions:
        return {
            "status": "exists",
            "message": f"{len(existing_sessions)} class sessions already exist for teacher {current_teacher.id}."
        }
    
    timetable = db.exec(select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == current_teacher.id)).all()
    academic = db.exec(select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)).all()

    if not timetable and academic:
        return {
            "status":"No timetable or academic calendar found, please create one first"
        }

    try:
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