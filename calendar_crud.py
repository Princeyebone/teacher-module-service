from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from dependencies import get_current_teacher
from database import get_db
from sqlmodel import Session, select
from model import TeacherProfile, AcademicCalendar, CalendarEvent
from schemas import AcademicCalendarEntry, AcademicCalendarPublic, CalendarEventPublic, UpdateCalendarResponse



router = APIRouter(prefix="/api")

@router.post("/create-academic-calendar/events")
async def create_calendar(
    data: UpdateCalendarResponse,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: Session = Depends(get_db)
):
    try:
        existing_calender = db.exec(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        ).first()
        if existing_calender:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Academic calendar already exists please delete before creating a new one."
            )

        new_calendar = AcademicCalendar(
            teacher_id=current_teacher.id,
            **data.academic_calendar.model_dump(exclude_unset=True)
        )

        db.add(new_calendar)
        db.commit()
        db.refresh(new_calendar)

        event_objs = []
        for event_data in data.calendar_events: 
            event_dict = event_data.model_dump(exclude_unset=True)

            event_obj = CalendarEvent(
                calender_id=new_calendar.id,  # link to the created calendar
                **event_dict
            )
            db.add(event_obj)
            event_objs.append(event_obj)
        db.commit()
        # Optionally refresh to get IDs
        for event_obj in event_objs:
            db.refresh(event_obj)
        
        events = db.exec(
            select(CalendarEvent).where(CalendarEvent.calender_id == new_calendar.id)
        ).all()
        
        return {
            "academic_calendar": AcademicCalendarPublic(
                id=new_calendar.id,
                teacher_id=new_calendar.teacher_id,
                semester_name=new_calendar.semester_name,
                academic_level=new_calendar.academic_level,
                semester_start_date=new_calendar.semester_start_date,
                mid_semester_break_start_date=new_calendar.mid_semester_break_start_date,
                mid_semester_break_end_date=new_calendar.mid_semester_break_end_date,
                semester_end_date=new_calendar.semester_end_date
            ),
            "calendar_events": [
                CalendarEventPublic(
                    id=e.id,
                    calender_id=e.calender_id,
                    event_name=e.event_name,
                    event_start_date=e.event_start_date,
                    event_end_date=e.event_end_date,
                    event_start_time=e.event_start_time,
                    event_end_time=e.event_end_time,
                    is_holiday=e.is_holiday,
                    requires_no_classes=e.requires_no_classes
                )
                for e in events
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating calendar: {e}"
        )

    
@router.get("/get-academic-calender/events")
async def get_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    try:
        calendar = db.exec(select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)).first()
        calendar_events = db.exec(select(CalendarEvent).where(CalendarEvent.calender_id == calendar.id)).all()

        if not calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No calendar found for this teacher"
            )
        return calendar, calendar_events
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve calendar: {e}"
        )
        

@router.patch("/update-academic-calendar/events")
async def update_calendar(
    payload: UpdateCalendarResponse,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    try:
        # Get the existing academic calendar
        existing_academic_calendar = db.exec(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        ).first()
        if not existing_academic_calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No academic calendar found for this teacher"
            )

        # Update academic calendar fields
        for key, value in payload.academic_calendar.model_dump(exclude_unset=True).items():
            setattr(existing_academic_calendar, key, value)
        db.add(existing_academic_calendar)
        db.commit()
        db.refresh(existing_academic_calendar)

        # Handle events: update existing, add new, remove missing
        # Get all existing events for this calendar
        existing_events = db.exec(
            select(CalendarEvent).where(CalendarEvent.calender_id == existing_academic_calendar.id)
        ).all()
        existing_events_dict = {e.id: e for e in existing_events}

        # Build a set of event IDs from the payload (if they exist)
        payload_event_ids = set()
        updated_events = []
        for event in payload.calendar_events:
            event_data = event.model_dump(exclude_unset=True)
            event_id = event_data.get("id")
            if event_id and event_id in existing_events_dict:
                # Update existing event
                db_event = existing_events_dict[event_id]
                for key, value in event_data.items():
                    if key != "id":
                        setattr(db_event, key, value)
                db.add(db_event)
                updated_events.append(db_event)
                payload_event_ids.add(event_id)
            else:
                # New event
                new_event = CalendarEvent(
                    calender_id=existing_academic_calendar.id, **event_data
                )
                db.add(new_event)
                db.commit()
                db.refresh(new_event)
                updated_events.append(new_event)

        # Delete events that are not in the payload
        for event in existing_events:
            if event.id not in payload_event_ids:
                db.delete(event)
        db.commit()

        # Get the latest list of events
        final_events = db.exec(
            select(CalendarEvent).where(CalendarEvent.calender_id == existing_academic_calendar.id)
        ).all()

        return {
            "academic_calendar": AcademicCalendarPublic(
                id=existing_academic_calendar.id,
                teacher_id=existing_academic_calendar.teacher_id,
                semester_name=existing_academic_calendar.semester_name,
                academic_level=existing_academic_calendar.academic_level,
                semester_start_date=existing_academic_calendar.semester_start_date,
                mid_semester_break_start_date=existing_academic_calendar.mid_semester_break_start_date,
                mid_semester_break_end_date=existing_academic_calendar.mid_semester_break_end_date,
                semester_end_date=existing_academic_calendar.semester_end_date
            ),
            "calendar_events": [
                CalendarEventPublic(
                    id=e.id,
                    calender_id=e.calender_id,
                    event_name=e.event_name,
                    event_start_date=e.event_start_date,
                    event_end_date=e.event_end_date,
                    event_start_time=e.event_start_time,
                    event_end_time=e.event_end_time,
                    is_holiday=e.is_holiday,
                    requires_no_classes=e.requires_no_classes
                )
                for e in final_events
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating calendar: {e}"
        )


@router.delete("/delete-academic-calender/events")
async def delete_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: Session = Depends(get_db)
):
    try:
        existing_calendar = db.exec(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        ).first()

        if not existing_calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar not found for this teacher"
            )

        # Delete all related events first
        related_events = db.exec(
            select(CalendarEvent).where(CalendarEvent.calender_id == existing_calendar.id)
        ).all()
        for event in related_events:
            db.delete(event)
        db.flush()  # Ensure events are deleted before calendar
        db.delete(existing_calendar)
        db.commit()
        return {"message": "Calendar deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting calendar: {e}"
        )