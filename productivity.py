# productivty.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request
from typing import Annotated
from model import TeacherProfile
from background import generate_schedule_task
from dependencies import get_current_teacher

router=APIRouter(tags=["Productivity"])


@router.post("/generate-schedule")
async def generate_schedule(
    country:str,
    current_teacher:Annotated[TeacherProfile, Depends(get_current_teacher)],
    
):      
    task = generate_schedule_task.delay(current_teacher.id,country )
    return {"task_id": task.id}
