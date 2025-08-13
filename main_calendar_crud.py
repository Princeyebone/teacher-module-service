from fastapi import APIRouter, HTTPException, Depends, status
from model import TeacherProfile, TeacherPlannerEvent, ClassSession, Calendar
from typing import Annotated
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from schemas import UpdateCalendar

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
    event: UpdateCalendar,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    try:
        calendar_objs = [
            Calendar(
                teacher_id=current_teacher.id,
                **item.model_dump(exclude_unset=True)
            )
            for item in event.items
        ]

        for obj in calendar_objs:
            db.add(obj)
        await db.commit()

        for obj in calendar_objs:
            await db.refresh(obj)
        return event.items
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch("/update-calendar")
async def update_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    event: UpdateCalendar,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Fetch existing entries for this teacher
        existing_entries = (await db.execute(
            select(Calendar).where(Calendar.teacher_id == current_teacher.id)
        )).scalars().all()
        existing_entries_dict = {e.id: e for e in existing_entries if e.id is not None}

        # Build a set of IDs from the payload (if they exist)
        payload_ids = set()
        updated_entries = []
        for item in event.items:
            item_data = item.model_dump(exclude_unset=True)
            item_id = item_data.get("id")
            if item_id and item_id in existing_entries_dict:
                # Update existing entry
                db_entry = existing_entries_dict[item_id]
                for key, value in item_data.items():
                    if key != "id":
                        setattr(db_entry, key, value)
                db.add(db_entry)
                updated_entries.append(db_entry)
                payload_ids.add(item_id)
            else:
                # New entry
                new_entry = Calendar(
                    teacher_id=current_teacher.id,
                    **item_data
                )
                db.add(new_entry)
                await db.commit()
                await db.refresh(new_entry)
                updated_entries.append(new_entry)

        # Delete entries that are not in the payload
        for entry in existing_entries:
            if entry.id not in payload_ids:
                await db.delete(entry)
        await db.commit()

        # Get the latest list of entries
        final_entries = (await db.execute(
            select(Calendar).where(Calendar.teacher_id == current_teacher.id)
        )).scalars().all()

        return final_entries

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating calendar: {str(e)}"
        )

@router.delete("/delete-calendar")
async def delete_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        # Delete all events for the current teacher
        events_to_delete = (await db.execute(
            select(Calendar).where(Calendar.teacher_id == current_teacher.id)
        )).scalars().all()
        
        for event in events_to_delete:
            await db.delete(event)
        await db.commit()
        return {"message": f"Deleted {len(events_to_delete)} calendar events"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )