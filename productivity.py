# productivty.py
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from model import TeacherProfile
from background import generate_schedule_task
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import Session, select

router=APIRouter(tags=["Productivity"])


@router.post("/generate-schedule")
async def generate_schedule(
    current_teacher:Annotated[TeacherProfile, Depends(get_current_teacher)],
    db:Session = Depends(get_db)
):

    teacher = db.exec(select(TeacherProfile).where(TeacherProfile.id == current_teacher.id)).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    country = teacher.country
    teacher_id = current_teacher.id

    """
    Triggers the background task to generate class sessions & teacher planner events.
    """
    try:
        result = generate_schedule_task.delay(teacher_id, country)
        return {
            "status": "processing",
            "message": f"Schedule generation started for teacher {teacher_id}.",
            "task_id": result.id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
