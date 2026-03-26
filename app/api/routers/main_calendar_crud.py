from fastapi import APIRouter, HTTPException, Depends, status, Path
from app.models.model import TeacherProfile, TeacherPlannerEvent, ClassSession, Calendar
from typing import Annotated
from app.core.dependencies import get_current_teacher
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.schemas.schemas import UpdateCalendar, Calendar as CalendarSchema

router = APIRouter(tags=["Calendar"])

@router.get("/read-school-calendar")
async def read_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        events = (await db.execute(
            select(TeacherPlannerEvent).where(TeacherPlannerEvent.teacher_id == current_teacher.id)
        )).scalars().all()
        
        if not events:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Fill Timetable and Academic Calendar then generate schedule"
            )
        
        return events
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/read-class-sessions")
async def read_class_sessions(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        class_sessions = (await db.execute(
            select(ClassSession).where(ClassSession.teacher_id == current_teacher.id)
        )).scalars().all()
        if not class_sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No class sessions found"
            )
        return class_sessions
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/read-calendar")
async def read_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        calendar = (await db.execute(
            select(Calendar).where(Calendar.teacher_id == current_teacher.id)
        )).scalars().all()
        if not calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No calendar found"
            )
        return calendar
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/create-event")
async def create_event(
    event: CalendarSchema,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        # Create a single calendar event
        calendar_obj = Calendar(
            teacher_id=current_teacher.id,
            **event.model_dump(exclude_unset=True)
        )

        db.add(calendar_obj)
        await db.commit()
        await db.refresh(calendar_obj)
        return calendar_obj
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/complete-calendar/{event_id}")
async def complete_calendar_event(
    event_id: Annotated[int, Path(title="The ID of the calendar event to complete")],
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        # Fetch the specific calendar event
        result = await db.execute(
            select(Calendar).where(
                Calendar.id == event_id,
                Calendar.teacher_id == current_teacher.id
            )
        )
        calendar_event = result.scalar_one_or_none()
        
        if not calendar_event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar event not found"
            )
        
        # Set the event as completed
        calendar_event.is_completed = True
        
        db.add(calendar_event)
        await db.commit()
        await db.refresh(calendar_event)
        return calendar_event
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/update-calendar/{event_id}")
async def update_calendar_event(
    event_id: Annotated[int, Path(title="The ID of the calendar event to update")],
    event: CalendarSchema,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        # Fetch the specific calendar event
        result = await db.execute(
            select(Calendar).where(
                Calendar.id == event_id,
                Calendar.teacher_id == current_teacher.id
            )
        )
        calendar_event = result.scalar_one_or_none()
        
        if not calendar_event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar event not found"
            )
        
        # Update the event with new data
        event_data = event.model_dump(exclude_unset=True)
        for key, value in event_data.items():
            setattr(calendar_event, key, value)
        
        db.add(calendar_event)
        await db.commit()
        await db.refresh(calendar_event)
        return calendar_event
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating calendar event: {str(e)}"
        )

@router.delete("/delete-calendar/{event_id}")
async def delete_calendar_event(
    event_id: Annotated[int, Path(title="The ID of the calendar event to delete")],
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        # Delete a specific event for the current teacher
        result = await db.execute(
            select(Calendar).where(
                Calendar.id == event_id,
                Calendar.teacher_id == current_teacher.id
            )
        )
        calendar_event = result.scalar_one_or_none()
        
        if not calendar_event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar event not found"
            )
        
        await db.delete(calendar_event)
        await db.commit()
        return {"message": f"Deleted calendar event with ID {event_id}"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )