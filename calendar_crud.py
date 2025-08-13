from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from model import TeacherProfile, AcademicCalendar, CalendarEvent
from schemas import AcademicCalendarEntry, AcademicCalendarPublic, CalendarEventPublic, UpdateCalendarResponse

router = APIRouter(prefix="/api")

@router.post("/create-academic-calendar/events")
async def create_calendar(
    data: UpdateCalendarResponse,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Check for existing calendar
        existing_calendar = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()
        if existing_calendar:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Academic calendar already exists. Please delete before creating a new one."
            )

        # Create new calendar
        new_calendar = AcademicCalendar(
            teacher_id=current_teacher.id,
            **data.academic_calendar.model_dump(exclude_unset=True)
        )
        db.add(new_calendar)
        await db.commit()
        await db.refresh(new_calendar)

        # Create events
        event_objs = []
        for event_data in data.calendar_events:
            event_dict = event_data.model_dump(exclude_unset=True)
            event_obj = CalendarEvent(
                calender_id=new_calendar.id,  # Link to the created calendar
                **event_dict
            )
            db.add(event_obj)
            event_objs.append(event_obj)
        await db.commit()

        # Optionally refresh events to get IDs
        for event_obj in event_objs:
            await db.refresh(event_obj)

        # Fetch events
        events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == new_calendar.id)
        )).scalars().all()

        return {
            "academic_calendar": AcademicCalendarPublic(
                id=new_calendar.id,
                teacher_id=new_calendar.teacher_id,
                semester_name=new_calendar.semester_name,
                academic_level=new_calendar.academic_level,
                midsem_exams_date=new_calendar.midsem_exams_date,
                revision_start_date=new_calendar.revision_start_date,
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
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating calendar: {str(e)}"
        )

@router.get("/get-academic-calendar/events")
async def get_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        calendar = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()
        if not calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No academic calendar found for this teacher"
            )

        calendar_events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == calendar.id)
        )).scalars().all()

        return {
            "academic_calendar": AcademicCalendarPublic(
                id=calendar.id,
                teacher_id=calendar.teacher_id,
                semester_name=calendar.semester_name,
                academic_level=calendar.academic_level,
                midsem_exams_date=calendar.midsem_exams_date,
                revision_start_date=calendar.revision_start_date,
                semester_start_date=calendar.semester_start_date,
                mid_semester_break_start_date=calendar.mid_semester_break_start_date,
                mid_semester_break_end_date=calendar.mid_semester_break_end_date,
                semester_end_date=calendar.semester_end_date
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
                for e in calendar_events
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve calendar: {str(e)}"
        )

@router.patch("/update-academic-calendar/events")
async def update_calendar(
    payload: UpdateCalendarResponse,
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        # Get the existing academic calendar
        existing_academic_calendar = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()
        if not existing_academic_calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No academic calendar found for this teacher"
            )

        # Update academic calendar fields
        for key, value in payload.academic_calendar.model_dump(exclude_unset=True).items():
            setattr(existing_academic_calendar, key, value)
        db.add(existing_academic_calendar)
        await db.commit()
        await db.refresh(existing_academic_calendar)

        # Handle events: update existing, add new, remove missing
        existing_events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == existing_academic_calendar.id)
        )).scalars().all()
        existing_events_dict = {e.id: e for e in existing_events}

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
                    calender_id=existing_academic_calendar.id,
                    **event_data
                )
                db.add(new_event)
                await db.commit()
                await db.refresh(new_event)
                updated_events.append(new_event)

        # Delete events that are not in the payload
        for event in existing_events:
            if event.id not in payload_event_ids:
                await db.delete(event)
        await db.commit()

        # Get the latest list of events
        final_events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == existing_academic_calendar.id)
        )).scalars().all()

        return {
            "academic_calendar": AcademicCalendarPublic(
                id=existing_academic_calendar.id,
                teacher_id=existing_academic_calendar.teacher_id,
                semester_name=existing_academic_calendar.semester_name,
                academic_level=existing_academic_calendar.academic_level,
                semester_start_date=existing_academic_calendar.semester_start_date,
                midsem_exams_date=existing_academic_calendar.midsem_exams_date,
                revision_start_date=existing_academic_calendar.revision_start_date,
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
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating calendar: {str(e)}"
        )

@router.delete("/delete-academic-calendar/events")
async def delete_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        existing_calendar = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()
        if not existing_calendar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Calendar not found for this teacher"
            )

        # Delete all related events
        related_events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == existing_calendar.id)
        )).scalars().all()
        for event in related_events:
            await db.delete(event)
        await db.delete(existing_calendar)
        await db.commit()
        return {"message": "Calendar deleted successfully"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting calendar: {str(e)}"
        )