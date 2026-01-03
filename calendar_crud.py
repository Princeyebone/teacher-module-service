from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from dependencies import get_current_teacher
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from model import TeacherProfile, AcademicCalendar, CalendarEvent, TempExtract, WeeklyTimeTable
from schemas import AcademicCalendarEntry, AcademicCalendarPublic, CalendarEventPublic, UpdateCalendarResponse
import logging

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
    """
    # DEBUG: Step-by-step to find greenlet issue
    logger.info("=== DEBUG: Starting calendar save ===")
    
    try:
        logger.info("DEBUG Step 1: Extracting teacher_id")
        teacher_id = current_teacher.id
        logger.info(f"DEBUG Step 1: SUCCESS - teacher_id = {teacher_id}")
    except Exception as e:
        logger.error(f"DEBUG Step 1 FAILED: {e}")
        raise HTTPException(status_code=400, detail=f"Step 1 failed: {e}")
    
    teacher_id_str = str(teacher_id)
    teacher_country = "Ghana"
    
    try:
        logger.info("DEBUG Step 2: Querying temp_entries")
        temp_entries = (await db.execute(
            select(TempExtract).where(
                TempExtract.teacher_id == teacher_id,
                TempExtract.type == "academic calendar"
            )
        )).scalars().all()
        logger.info(f"DEBUG Step 2: SUCCESS - found {len(temp_entries)} temp entries")
        
        logger.info("DEBUG Step 3: Deleting temp entries")
        for entry in temp_entries:
            await db.delete(entry)
        logger.info("DEBUG Step 3: SUCCESS")

        logger.info("DEBUG Step 4: Querying existing calendar")
        existing_calendar = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == teacher_id)
        )).scalar_one_or_none()
        logger.info(f"DEBUG Step 4: SUCCESS - existing_calendar = {existing_calendar is not None}")

        logger.info("DEBUG Step 5: Creating/updating calendar")
        if existing_calendar:
            for key, value in data.academic_calendar.model_dump(exclude_unset=True).items():
                setattr(existing_calendar, key, value)
            db.add(existing_calendar)
            new_calendar = existing_calendar
        else:
            new_calendar = AcademicCalendar(
                teacher_id=teacher_id,
                **data.academic_calendar.model_dump(exclude_unset=True)
            )
            db.add(new_calendar)
        logger.info("DEBUG Step 5: SUCCESS")
        
        logger.info("DEBUG Step 6: Flushing")
        await db.flush()
        logger.info(f"DEBUG Step 6: SUCCESS - new_calendar.id = {new_calendar.id}")
        
        logger.info("DEBUG Step 7: Querying existing events")
        existing_events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == new_calendar.id)
        )).scalars().all()
        existing_events_dict = {e.id: e for e in existing_events}
        logger.info(f"DEBUG Step 7: SUCCESS - found {len(existing_events)} events")

        logger.info("DEBUG Step 8: Processing events")
        payload_event_ids = set()
        for event in data.calendar_events:
            event_data = event.model_dump(exclude_unset=True)
            event_id = event_data.get("id")
            if event_id and event_id in existing_events_dict:
                db_event = existing_events_dict[event_id]
                for key, value in event_data.items():
                    if key != "id":
                        setattr(db_event, key, value)
                db.add(db_event)
                payload_event_ids.add(event_id)
            else:
                event_data.pop("id", None)
                new_event = CalendarEvent(
                    calender_id=new_calendar.id,
                    **event_data
                )
                db.add(new_event)
        logger.info("DEBUG Step 8: SUCCESS")

        logger.info("DEBUG Step 9: Deleting old events")
        for event in existing_events:
            if event.id not in payload_event_ids:
                await db.delete(event)
        logger.info("DEBUG Step 9: SUCCESS")
        
        logger.info("DEBUG Step 10: Extracting calendar dict")
        calendar_dict = {
            "id": new_calendar.id,
            "teacher_id": new_calendar.teacher_id,
            "semester_name": new_calendar.semester_name,
            "midsem_exams_date": new_calendar.midsem_exams_date,
            "revision_start_date": new_calendar.revision_start_date,
            "semester_start_date": new_calendar.semester_start_date,
            "mid_semester_break_start_date": new_calendar.mid_semester_break_start_date,
            "mid_semester_break_end_date": new_calendar.mid_semester_break_end_date,
            "semester_end_date": new_calendar.semester_end_date
        }
        # IMPORTANT: Save calendar ID before commit - after commit, accessing new_calendar.id triggers lazy load which fails in async
        calendar_id = new_calendar.id
        logger.info("DEBUG Step 10: SUCCESS")
        
        logger.info("DEBUG Step 11: Committing")
        await db.commit()
        logger.info("DEBUG Step 11: SUCCESS")
        
        logger.info("DEBUG Step 12: Re-fetching events")
        final_events = (await db.execute(
            select(CalendarEvent).where(CalendarEvent.calender_id == calendar_id)  # Use saved ID, not new_calendar.id
        )).scalars().all()
        logger.info(f"DEBUG Step 12: SUCCESS - found {len(final_events)} events")
        
        logger.info("DEBUG Step 13: Building events list")
        events_list = []
        for e in final_events:
            events_list.append({
                "id": e.id,
                "calender_id": e.calender_id,
                "event_name": e.event_name,
                "event_start_date": e.event_start_date,
                "event_end_date": e.event_end_date,
                "event_start_time": e.event_start_time,
                "event_end_time": e.event_end_time,
                "is_holiday": e.is_holiday,
                "requires_no_classes": e.requires_no_classes
            })
        logger.info("DEBUG Step 13: SUCCESS")
        
        logger.info("DEBUG Step 14: Building response")
        response_data = {
            "academic_calendar": AcademicCalendarPublic(**calendar_dict),
            "calendar_events": [CalendarEventPublic(**ev) for ev in events_list]
        }
        logger.info("DEBUG Step 14: SUCCESS")

    except Exception as e:
        import traceback
        logger.error(f"DEBUG EXCEPTION: {e}")
        logger.error(f"DEBUG TRACEBACK: {traceback.format_exc()}")
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.error(f"DEBUG ROLLBACK FAILED: {rollback_error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating/updating calendar: {str(e)}"
        )
    
    logger.info("DEBUG Step 15: Enqueuing schedule generation")
    from enque_task import enqueue_schedule_generation
    try:
        job_id = await enqueue_schedule_generation(teacher_id_str, teacher_country)
        if job_id:
            logger.info(f"✅ Session generation job enqueued: {job_id}")
        else:
            logger.warning(f"⚠️ Session generation job returned None")
    except Exception as e:
        logger.error(f"❌ Failed to enqueue session generation: {e}")

    logger.info("DEBUG Step 16: Returning response")
    return response_data

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