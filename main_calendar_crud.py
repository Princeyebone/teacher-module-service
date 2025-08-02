from fastapi import APIRouter, HTTPException, Depends, status
from model import TeacherProfile, TeacherPlannerEvent, ClassSession, Calendar
from typing import Annotated
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import Session, select
from schemas import UpdateCalendar
 


router = APIRouter(tags=["Calendar"])

@router.get("/read-school-calendar")
async def read_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Annotated[Session, Depends(get_db)]
):
    try:
        events = db.exec(
            select(TeacherPlannerEvent).where(TeacherPlannerEvent.teacher_id == current_teacher.id)
        ).all()
        
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
    current_teacher:Annotated[TeacherProfile, Depends(get_current_teacher)],
    db:Annotated[Session, Depends(get_db)]
):
    try:
        class_sessions= db.exec(select(ClassSession).where(ClassSession.teacher_id == current_teacher.id)).all()
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
    current_teacher:Annotated[TeacherProfile, Depends(get_current_teacher)],
    db:Annotated[Session, Depends(get_db)]
):
    try:
        calendar= db.exec(select(Calendar).where(Calendar.teacher_id == current_teacher.id)).all()
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
    db: Annotated[Session, Depends(get_db)]
):
    try:
        records = [
            {**item.model_dump(), "teacher_id": current_teacher.id}
            for item in event.items
        ]

        db.bulk_insert_mappings(Calendar, records)
        db.commit()
        return event.items
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    
@router.patch("/update-calendar")
async def update_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    event: UpdateCalendar,
    db: Session = Depends(get_db)
):
    try:
        # Fetch existing entries for this teacher
        existing_entries = db.exec(
            select(Calendar).where(Calendar.teacher_id == current_teacher.id)
        ).all()
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
                    teacher_id=current_teacher.id, **item_data
                )
                db.add(new_entry)
                db.commit()
                db.refresh(new_entry)
                updated_entries.append(new_entry)

        # Delete entries that are not in the payload
        for entry in existing_entries:
            if entry.id not in payload_ids:
                db.delete(entry)
        db.commit()

        # Get the latest list of entries
        final_entries = db.exec(
            select(Calendar).where(Calendar.teacher_id == current_teacher.id)
        ).all()

        return final_entries

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating calendar: {e}"
        )

    
@router.delete("/delete-calendar")
async def delete_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    try:
        # Delete all events for the current teacher
        events_to_delete = db.exec(
            select(Calendar).where(Calendar.teacher_id == current_teacher.id)
        ).all()
        
        for event in events_to_delete:
            db.delete(event)
        
        db.commit()
        return {"message": f"Deleted {len(events_to_delete)} calendar events"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )




