from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from model import TeacherProfile, AcademicCalendar, CalendarEvent, TempExtract, WeeklyTimeTable
from schemas import AcademicCalendarEntry, AcademicCalendarPublic, CalendarEventPublic, UpdateCalendarResponse
import logging
from schedule_utils import check_and_trigger_session_generation

# Initialize logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/academic-calendar/events")
async def create_or_update_calendar(
    data: UpdateCalendarResponse,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Create or update academic calendar events.
    If calendar exists, update it. If not, create new one.
    Also removes any academic calendar type entry for this teacher_id in the tempextract db table.
    """
    try:
        # Remove any academic calendar type entry for this teacher_id in the tempextract db table
        temp_entries = (await db.execute(
            select(TempExtract).where(
                TempExtract.teacher_id == current_teacher.id,
                TempExtract.type == "academic calendar"
            )
        )).scalars().all()
        
        for entry in temp_entries:
            await db.delete(entry)
        if temp_entries:
            await db.commit()
            logger.info(f"🗑️ Removed {len(temp_entries)} academic calendar temp entries for teacher {current_teacher.id}")

        # Check for existing calendar
        existing_calendar = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()

        if existing_calendar:
            # Update existing calendar
            logger.info(f"Updating existing calendar for teacher {current_teacher.id}")
            for key, value in data.academic_calendar.model_dump(exclude_unset=True).items():
                setattr(existing_calendar, key, value)
            db.add(existing_calendar)
            await db.commit()
            await db.refresh(existing_calendar)
            new_calendar = existing_calendar
        else:
            # Create new calendar
            logger.info(f"Creating new calendar for teacher {current_teacher.id}")
            new_calendar = AcademicCalendar(
                teacher_id=current_teacher.id,
                **data.academic_calendar.model_dump(exclude_unset=True)
            )
            db.add(new_calendar)
            await db.commit()
            await db.refresh(new_calendar)

        # Handle events: update existing, add new, remove missing
        existing_events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == new_calendar.id)
        )).scalars().all()
        existing_events_dict = {e.id: e for e in existing_events}

        payload_event_ids = set()
        updated_events = []
        for event in data.calendar_events:
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
                    calender_id=new_calendar.id,
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
            select(CalendarEvent).where(CalendarEvent.calender_id == new_calendar.id)
        )).scalars().all()
        
        response_data = {
            "academic_calendar": AcademicCalendarPublic(
                id=new_calendar.id,
                teacher_id=new_calendar.teacher_id,
                semester_name=new_calendar.semester_name,
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
                for e in final_events
            ]
        }
        
        # Trigger session generation after successful save
        # We do this after the main transaction is complete to avoid session issues
        from schedule_utils import trigger_session_generation_after_save
        await trigger_session_generation_after_save(str(current_teacher.id))
        
        return response_data

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating/updating calendar: {str(e)}"
        )

@router.get("/get-academic-calendar/events")
async def get_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    try:
        # First check if there's temporary extracted data
        temp_extract = (await db.execute(
            select(TempExtract).where(
                TempExtract.teacher_id == current_teacher.id,
                TempExtract.type == "academic calendar"
            )
        )).scalar_one_or_none()
        
        if temp_extract:
            # Use temporary data
            calendar_data = temp_extract.data.get("academic_calendar", {})
            calendar_events = temp_extract.data.get("calendar_events", [])
            
            if not calendar_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No academic calendar found for this teacher"
                )
            
            # Return the data with source information
            return {
                "academic_calendar": calendar_data,
                "calendar_events": calendar_events,
                "data_source": "temp_extract"
            }
        else:
            # Fall back to permanent calendar data
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
                ],
                "data_source": "academic_calendar"
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not retrieve calendar: {str(e)}"
        )

@router.delete("/delete-academic-calendar/events")
async def delete_calendar(
    current_teacher: Annotated[TeacherProfile, Depends(get_current_teacher)],
    db: AsyncSession = Depends(get_db)
):
    """
    Delete academic calendar and remove any academic calendar type entry for this teacher_id in the tempextract db table.
    """
    try:
        # Remove any academic calendar type entry for this teacher_id in the tempextract db table
        temp_entries = (await db.execute(
            select(TempExtract).where(
                TempExtract.teacher_id == current_teacher.id,
                TempExtract.type == "academic calendar"
            )
        )).scalars().all()
        
        for entry in temp_entries:
            await db.delete(entry)
        if temp_entries:
            logger.info(f"🗑️ Removed {len(temp_entries)} academic calendar temp entries for teacher {current_teacher.id}")

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
        
        # Delete the calendar itself
        await db.delete(existing_calendar)
        await db.commit()
        
        return {"message": "Calendar deleted successfully"}

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting calendar: {str(e)}"
        )