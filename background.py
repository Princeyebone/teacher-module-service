from celery_app import celery_app
from sqlmodel import select
from database import async_engine
from model import (
    AcademicCalendar, WeeklyTimeTable, CalendarEvent,
    ClassSession, TeacherPlannerEvent, TeacherNotification
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from datetime import timedelta, date, datetime
from external_service import get_holidays_from_ai
import redis
import json
from uuid import UUID
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- REDIS CLIENT ---------------- #
redis_client = redis.StrictRedis(host="localhost", port=6379, decode_responses=True)

# ---------------- DATABASE UTILS ---------------- #
async def get_celery_session():
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session

# ---------------- PUBLISH TO WS + SAVE NOTIFICATION ---------------- #
async def save_notification(teacher_id: str, title: str, message: str, type_: str = "info"):
    """Saves notification to TeacherNotification table."""
    logger.debug(f"Saving notification for teacher {teacher_id}: {title}")
    async with async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)() as session:
        try:
            notification = TeacherNotification(
                teacher_id=UUID(teacher_id),
                title=title,
                message=message,
                type=type_,
                created_at=datetime.utcnow(),
                is_read=False
            )
            session.add(notification)
            await session.commit()
            logger.info(f"Notification saved for teacher {teacher_id}: {title}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Error saving notification: {str(e)}")
            raise

async def publish_ws_message(teacher_id: str, message: dict):
    """
    Publish a message to WebSocket via Redis AND save a notification to DB.
    """
    logger.debug(f"Publishing WebSocket message for teacher {teacher_id}: {message}")
    title = "Schedule Update" if message.get("status") != "error" else "Error Occurred"
    try:
        await save_notification(
            teacher_id=teacher_id,
            title=title,
            message=message.get("message", "Notification"),
            type_="error" if message.get("status") == "error" else "info"
        )
    except Exception as e:
        logger.error(f"Failed to save notification: {str(e)}")
        raise

    try:
        redis_client.publish(f"ws:{teacher_id}", json.dumps(message))
        logger.info(f"[Redis] Published to ws:{teacher_id}: {message}")
    except Exception as e:
        logger.error(f"Redis publish error: {str(e)}")
        raise

# ---------------- CONSTANTS ---------------- #
WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# ---------------- CLASS SESSION GENERATION ---------------- #
def generate_class_dates(semester_start, semester_end, timetable):
    """Generates all possible class sessions between semester dates."""
    sessions = []
    for entry in timetable:
        weekday_num = WEEKDAY_MAP[entry.weekday.lower()]
        current_date = semester_start
        session_counter = 1

        while current_date <= semester_end:
            if current_date.weekday() == weekday_num:
                sessions.append({
                    "subject": entry.subject,
                    "date": current_date,  # Store as date object
                    "start_time": entry.start_time.strftime("%H:%M"),
                    "end_time": entry.end_time.strftime("%H:%M"),
                    "class_name": entry.pupils,
                    "location": entry.pupils,
                    "session_number": session_counter
                })
                session_counter += 1
            current_date += timedelta(days=1)
    logger.debug(f"Generated {len(sessions)} sessions with date objects")
    return sessions

def filter_sessions(sessions, events, holidays, calendar=None):
    """Filters out sessions that fall on holidays, events, breaks, revision period."""
    no_class_dates = set()

    if calendar and calendar.mid_semester_break_start_date and calendar.mid_semester_break_end_date:
        current = calendar.mid_semester_break_start_date
        while current <= calendar.mid_semester_break_end_date:
            no_class_dates.add(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

    if calendar and calendar.midsem_exams_date:
        no_class_dates.add(calendar.midsem_exams_date.strftime("%Y-%m-%d"))

    revision_cutoff = None
    if calendar and calendar.revision_start_date:
        revision_cutoff = calendar.revision_start_date

    for e in events:
        is_holiday = getattr(e, "is_holiday", False)
        requires_no_classes = getattr(e, "requires_no_classes", False)
        if is_holiday or requires_no_classes:
            start = getattr(e, "event_start_date", None)
            end = getattr(e, "event_end_date", start)
            if start:
                current = start
                while current <= end:
                    no_class_dates.add(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)

    for h in holidays:
        if h.get("requires_no_classes", True):
            no_class_dates.add(h["date"])

    logger.info(f"No-class dates: {sorted(no_class_dates)}")

    filtered = []
    for s in sessions:
        session_date_str = s["date"].strftime("%Y-%m-%d")
        if revision_cutoff and s["date"] >= revision_cutoff:
            continue
        if session_date_str in no_class_dates:
            continue
        filtered.append(s)
    logger.debug(f"Filtered to {len(filtered)} sessions")
    return filtered

async def populate_teacher_planner_events(teacher_id, calendar, events, holidays):
    """Populates TeacherPlannerEvent table with milestones, events & holidays."""
    logger.debug(f"Populating planner events for teacher {teacher_id}")
    async with async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)() as session:
        try:
            milestones = [
                {
                    "date": calendar.semester_start_date,
                    "title": "Semester Begins",
                    "description": f"Start of {calendar.semester_name}",
                    "event_type": "academic",
                    "is_required": True,
                    "start_time": None,
                    "end_time": None
                },
                {
                    "date": calendar.semester_end_date,
                    "title": "Semester Ends",
                    "description": f"End of {calendar.semester_name}",
                    "event_type": "academic",
                    "is_required": True,
                    "start_time": None,
                    "end_time": None
                }
            ]

            if calendar.mid_semester_break_start_date and calendar.mid_semester_break_end_date:
                current = calendar.mid_semester_break_start_date
                while current <= calendar.mid_semester_break_end_date:
                    milestones.append({
                        "date": current,
                        "title": "Mid-Semester Break",
                        "description": "No classes (mid-semester break)",
                        "event_type": "break",
                        "is_required": False,
                        "start_time": None,
                        "end_time": None
                    })
                    current += timedelta(days=1)

            if calendar.midsem_exams_date:
                milestones.append({
                    "date": calendar.midsem_exams_date,
                    "title": "Mid-Semester Exam",
                    "description": "Mid-semester examinations",
                    "event_type": "exam",
                    "is_required": False,
                    "start_time": None,
                    "end_time": None
                })

            if calendar.revision_start_date:
                milestones.append({
                    "date": calendar.revision_start_date,
                    "title": "Revision Period Begins",
                    "description": "Start of revision, no regular classes",
                    "event_type": "revision",
                    "is_required": False,
                    "start_time": None,
                    "end_time": None
                })

            academic_event_entries = []
            for e in events:
                start = e.event_start_date
                end = getattr(e, "event_end_date", e.event_start_date)
                current = start
                while current <= end:
                    academic_event_entries.append({
                        "date": current,
                        "title": e.event_name or "Academic Event",
                        "description": f"Event: {e.event_name}",
                        "event_type": "academic_event",
                        "is_required": not (e.requires_no_classes or e.is_holiday),
                        "start_time": getattr(e, "event_start_time", None),
                        "end_time": getattr(e, "event_end_time", None)
                    })
                    current += timedelta(days=1)

            holiday_entries = [
                {
                    "date": date.fromisoformat(h["date"]),
                    "title": h["name"],
                    "description": h.get("description", ""),
                    "event_type": "holiday",
                    "is_required": not h.get("requires_no_classes", True),
                    "start_time": None,
                    "end_time": None
                }
                for h in holidays
            ]

            all_entries = milestones + academic_event_entries + holiday_entries

            for ev in all_entries:
                logger.debug(f"Checking for existing event: {ev['title']} on {ev['date']}")
                existing = (await session.execute(
                    select(TeacherPlannerEvent).where(
                        TeacherPlannerEvent.teacher_id == teacher_id,
                        TeacherPlannerEvent.date == ev["date"],
                        TeacherPlannerEvent.title == ev["title"]
                    )
                )).scalar_one_or_none()

                if not existing:
                    session.add(TeacherPlannerEvent(
                        teacher_id=teacher_id,
                        date=ev["date"],
                        start_time=ev["start_time"],
                        end_time=ev["end_time"],
                        title=ev["title"],
                        description=ev["description"],
                        event_type=ev["event_type"],
                        is_required=ev["is_required"]
                    ))

            await session.commit()
            logger.info(f"{len(all_entries)} events saved/updated in TeacherPlannerEvent.")
        except Exception as e:
            await session.rollback()
            logger.error(f"Error saving TeacherPlannerEvents: {str(e)}")
            raise

# ---------------- CELERY TASK ---------------- #
@celery_app.task(name="teacher_scheduler.generate_schedule_task")
def generate_schedule_task(teacher_id: str, country: str):
    logger.info(f"Starting generate_schedule_task for teacher: {teacher_id}")
    
    async def async_task():
        async with async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)() as session:
            try:
                await publish_ws_message(teacher_id, {
                    "status": "started",
                    "message": "Generating schedule...",
                    "teacher_id": teacher_id
                })

                logger.debug(f"Fetching calendar for teacher: {teacher_id}")
                calendar = (await session.execute(
                    select(AcademicCalendar).where(AcademicCalendar.teacher_id == teacher_id)
                )).scalar_one_or_none()
                if not calendar:
                    error_msg = "No academic calendar found."
                    logger.error(error_msg)
                    await publish_ws_message(teacher_id, {
                        "status": "error",
                        "message": error_msg,
                        "teacher_id": teacher_id
                    })
                    return {"error": error_msg}

                logger.debug(f"Fetching timetable for teacher: {teacher_id}")
                timetable = (await session.execute(
                    select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == teacher_id)
                )).scalars().all()
                if not timetable:
                    error_msg = "No timetable found."
                    logger.error(error_msg)
                    await publish_ws_message(teacher_id, {
                        "status": "error",
                        "message": error_msg,
                        "teacher_id": teacher_id
                    })
                    return {"error": error_msg}

                logger.debug(f"Fetching events for calendar: {calendar.id}")
                events = (await session.execute(
                    select(CalendarEvent).where(CalendarEvent.calender_id == calendar.id)
                )).scalars().all()
                logger.info(f"Found: {len(timetable)} timetable entries, {len(events)} events")

                # Generate Sessions
                logger.debug("Generating class sessions...")
                deterministic_sessions = generate_class_dates(
                    calendar.semester_start_date,
                    calendar.semester_end_date,
                    timetable
                )
                logger.info(f"Generated {len(deterministic_sessions)} sessions before filtering")

                # Get holidays with timeout protection
                logger.debug(f"Fetching holidays for {country}...")
                try:
                    import threading
                    holidays = []
                    holiday_error = None

                    def fetch_holidays():
                        nonlocal holidays, holiday_error
                        try:
                            holidays = get_holidays_from_ai(country, calendar.semester_start_date.year)
                        except Exception as e:
                            holiday_error = e

                    thread = threading.Thread(target=fetch_holidays)
                    thread.daemon = True
                    thread.start()
                    thread.join(timeout=30)

                    if thread.is_alive():
                        logger.warning("Holiday fetch timed out, using empty list")
                        holidays = []
                    elif holiday_error:
                        logger.warning(f"Error fetching holidays: {holiday_error}, using empty list")
                        holidays = []
                    else:
                        logger.info(f"Fetched {len(holidays)} holidays")
                except Exception as e:
                    logger.warning(f"Error in holiday fetch setup: {e}, using empty list")
                    holidays = []

                # Filter sessions
                logger.debug("Filtering sessions...")
                filtered_sessions = filter_sessions(deterministic_sessions, events, holidays, calendar)
                logger.info(f"{len(filtered_sessions)} sessions remain after filtering")

                # Clear existing sessions for this teacher
                logger.debug("Clearing existing sessions...")
                existing_sessions = (await session.execute(
                    select(ClassSession).where(ClassSession.teacher_id == teacher_id)
                )).scalars().all()
                for session_obj in existing_sessions:
                    await session.delete(session_obj)
                await session.commit()
                logger.info(f"Cleared {len(existing_sessions)} existing sessions")

                # Save new sessions
                logger.debug("Saving new sessions...")
                for cs in filtered_sessions:
                    session.add(ClassSession(
                        teacher_id=teacher_id,
                        subject=cs["subject"],
                        date=cs["date"],  # Use date object directly
                        start_time=cs["start_time"],
                        end_time=cs["end_time"],
                        class_name=cs["class_name"],
                        session_number=cs["session_number"],
                        is_completed=False,
                        resource_generated=False,
                        location=cs["location"]
                    ))
                await session.commit()
                logger.info(f"{len(filtered_sessions)} sessions saved to ClassSession")

                # Populate planner events
                logger.debug("Populating planner events...")
                await populate_teacher_planner_events(teacher_id, calendar, events, holidays)
                logger.info("Planner events populated")

                success_msg = f"Schedule generation complete! {len(filtered_sessions)} sessions created"
                logger.info(success_msg)
                await publish_ws_message(teacher_id, {
                    "status": "completed",
                    "message": success_msg,
                    "teacher_id": teacher_id,
                    "details": {
                        "sessions_saved": len(filtered_sessions),
                    }
                })

                return {"status": "success", "class_sessions_saved": len(filtered_sessions)}
            except Exception as e:
                error_msg = f"Error in async task: {str(e)}"
                logger.error(error_msg)
                await publish_ws_message(teacher_id, {
                    "status": "error",
                    "message": error_msg,
                    "teacher_id": teacher_id
                })
                return {"error": error_msg}

    try:
        result = asyncio.run(async_task())
        logger.debug(f"Task result: {result}")
        return result
    except RuntimeError as e:
        logger.error(f"Event loop error: {str(e)}")
        return {"error": f"Event loop error: {str(e)}"}

# ✅ Manual Run (for testing)
if __name__ == "__main__":
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    result = generate_schedule_task.delay(teacher_id, country="Ghana")
    print("✅ Task queued:", result.id)



