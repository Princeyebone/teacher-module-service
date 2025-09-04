from arq import create_pool, ArqRedis
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Handle imports for both direct execution and module import
try:
    from config import settings
    from logger import logger
    from model import (
        AcademicCalendar, WeeklyTimeTable, CalendarEvent,
        ClassSession, TeacherPlannerEvent, TeacherNotification
    )
    from external_service import get_holidays_from_ai
except ImportError:
    # If running as script directly, add parent directory to path
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    from config import settings
    from logger import logger
    from model import (
        AcademicCalendar, WeeklyTimeTable, CalendarEvent,
        ClassSession, TeacherPlannerEvent, TeacherNotification
    )
    from external_service import get_holidays_from_ai

from sqlalchemy import select
from datetime import timedelta, date, datetime
import redis.asyncio as redis
import json
from uuid import UUID
import logging
import traceback
import asyncio
from asyncpg.exceptions import InterfaceError, ConnectionFailureError, ClientCannotConnectError


# Initialize async Redis client for WebSocket
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

# Initialize SQLAlchemy async engine
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=5,
    pool_recycle=180,
    pool_pre_ping=True
)

# Arq Redis settings
arq_redis_settings = RedisSettings(host="localhost", port=6379)

# ---------------- DATABASE UTILS ---------------- #
async def get_session():
    async with AsyncSession(async_engine) as session:
        yield session

# ---------------- PUBLISH TO WS + SAVE NOTIFICATION ---------------- #
async def save_notification(teacher_id: str, title: str, message: str, type_: str = "info"):
    """Saves notification to TeacherNotification table."""
    logger.debug(f"Saving notification for teacher {teacher_id}: {title}")
    max_attempts = 2
    async with async_engine.connect() as conn:
        async with AsyncSession(async_engine) as session:
            for attempt in range(max_attempts):
                try:
                    async with session.begin():
                        notification = TeacherNotification(
                            teacher_id=UUID(teacher_id),
                            title=title,
                            message=message,
                            type=type_,
                            created_at=datetime.utcnow(),
                            is_read=False
                        )
                        session.add(notification)
                        await asyncio.wait_for(session.commit(), timeout=5.0)
                        logger.info(f"Notification saved for teacher {teacher_id}: {title}")
                        return
                except (ClientCannotConnectError, InterfaceError, ConnectionFailureError, asyncio.TimeoutError) as e:
                    await session.rollback()
                    logger.warning(f"Connection error on attempt {attempt + 1}/{max_attempts}: {str(e)}\n{traceback.format_exc()}")
                    if attempt == max_attempts - 1:
                        logger.error(f"Failed to save notification after {max_attempts} attempts: {str(e)}\n{traceback.format_exc()}")
                        raise
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Unexpected error saving notification: {str(e)}\n{traceback.format_exc()}")
                    raise
                finally:
                    await session.close()
                    await conn.close()

async def publish_ws_message(teacher_id: str, message: dict):
    """Publish a message to WebSocket via Redis AND save a notification to DB."""
    logger.debug(f"Publishing WebSocket message for teacher {teacher_id}: {message}")
    title = "Schedule Update" if message.get("status") != "error" else "Error Occurred"
    try:
        await save_notification(
            teacher_id=teacher_id,
            title=title,
            message=message.get("message", "Notification"),
            type_="error" if message.get("status") == "error" else "info"
        )
        await redis_client.publish(f"ws:{teacher_id}", json.dumps(message))
        logger.info(f"[Redis] Published to ws:{teacher_id}: {message}")
    except Exception as e:
        logger.error(f"Failed to publish WebSocket message: {str(e)}\n{traceback.format_exc()}")
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
                    "date": current_date,
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

def filter_sessions(sessions, events_data, holidays, calendar_data=None):
    """Filters out sessions that fall on holidays, events, breaks, revision period."""
    no_class_dates = set()
    if calendar_data and calendar_data.get("mid_semester_break_start_date") and calendar_data.get("mid_semester_break_end_date"):
        current = calendar_data["mid_semester_break_start_date"]
        while current <= calendar_data["mid_semester_break_end_date"]:
            no_class_dates.add(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
    if calendar_data and calendar_data.get("midsem_exams_date"):
        no_class_dates.add(calendar_data["midsem_exams_date"].strftime("%Y-%m-%d"))
    revision_cutoff = calendar_data.get("revision_start_date") if calendar_data else None
    for e in events_data:
        is_holiday = e.get("is_holiday", False)
        requires_no_classes = e.get("requires_no_classes", False)
        if is_holiday or requires_no_classes:
            start = e.get("event_start_date")
            end = e.get("event_end_date", start)
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

async def populate_teacher_planner_events(teacher_id, calendar_data, events_data, holidays):
    """Populates TeacherPlannerEvent table with milestones, events & holidays."""
    logger.debug(f"Populating planner events for teacher {teacher_id}")
    async with async_engine.connect() as conn:
        async with AsyncSession(async_engine) as session:
            try:
                async with session.begin():
                    milestones = [
                        {
                            "date": calendar_data["semester_start_date"],
                            "title": "Semester Begins",
                            "description": f"Start of {calendar_data['semester_name']}",
                            "event_type": "academic",
                            "is_required": True,
                            "start_time": None,
                            "end_time": None
                        },
                        {
                            "date": calendar_data["semester_end_date"],
                            "title": "Semester Ends",
                            "description": f"End of {calendar_data['semester_name']}",
                            "event_type": "academic",
                            "is_required": True,
                            "start_time": None,
                            "end_time": None
                        }
                    ]
                    if calendar_data.get("mid_semester_break_start_date") and calendar_data.get("mid_semester_break_end_date"):
                        current = calendar_data["mid_semester_break_start_date"]
                        while current <= calendar_data["mid_semester_break_end_date"]:
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
                    if calendar_data.get("midsem_exams_date"):
                        milestones.append({
                            "date": calendar_data["midsem_exams_date"],
                            "title": "Mid-Semester Exam",
                            "description": "Mid-semester examinations",
                            "event_type": "exam",
                            "is_required": False,
                            "start_time": None,
                            "end_time": None
                        })
                    if calendar_data.get("revision_start_date"):
                        milestones.append({
                            "date": calendar_data["revision_start_date"],
                            "title": "Revision Period Begins",
                            "description": "Start of revision, no regular classes",
                            "event_type": "revision",
                            "is_required": False,
                            "start_time": None,
                            "end_time": None
                        })
                    academic_event_entries = []
                    for e in events_data:
                        start = e.get("event_start_date")
                        end = e.get("event_end_date", start)
                        current = start
                        while current <= end:
                            academic_event_entries.append({
                                "date": current,
                                "title": e.get("event_name", "Academic Event"),
                                "description": f"Event: {e.get('event_name', 'Academic Event')}",
                                "event_type": "academic_event",
                                "is_required": not (e.get("requires_no_classes", False) or e.get("is_holiday", False)),
                                "start_time": e.get("event_start_time"),
                                "end_time": e.get("event_end_time")
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
                    await asyncio.wait_for(session.commit(), timeout=5.0)
                    logger.info(f"{len(all_entries)} events saved/updated in TeacherPlannerEvent.")
            except (ClientCannotConnectError, InterfaceError, ConnectionFailureError, asyncio.TimeoutError) as e:
                await session.rollback()
                logger.error(f"Connection error saving TeacherPlannerEvents: {str(e)}\n{traceback.format_exc()}")
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"Unexpected error saving TeacherPlannerEvents: {str(e)}\n{traceback.format_exc()}")
                raise
            finally:
                await session.close()
                await conn.close()

# ---------------- ARQ TASK ---------------- #
async def generate_schedule_task(ctx: dict, teacher_id: str, country: str):
    logger.info(f"Starting generate_schedule_task for teacher: {teacher_id}")
    try:
        # Initial WebSocket message
        await publish_ws_message(teacher_id, {
            "status": "started",
            "message": "Generating schedule...",
            "teacher_id": teacher_id
        })
        async with async_engine.connect() as conn:
            async with AsyncSession(async_engine) as session:
                try:
                    async with session.begin():
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
                        # Extract calendar attributes to avoid detached object
                        calendar_data = {
                            "semester_name": calendar.semester_name,
                            "semester_start_date": calendar.semester_start_date,
                            "semester_end_date": calendar.semester_end_date,
                            "mid_semester_break_start_date": calendar.mid_semester_break_start_date,
                            "mid_semester_break_end_date": calendar.mid_semester_break_end_date,
                            "midsem_exams_date": calendar.midsem_exams_date,
                            "revision_start_date": calendar.revision_start_date
                        }
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
                        # Extract events attributes to avoid detached objects
                        events_data = [
                            {
                                "event_name": e.event_name,
                                "event_start_date": e.event_start_date,
                                "event_end_date": e.event_end_date,
                                "event_start_time": e.event_start_time,
                                "event_end_time": e.event_end_time,
                                "is_holiday": e.is_holiday,
                                "requires_no_classes": e.requires_no_classes
                            }
                            for e in events
                        ]
                        logger.info(f"Found: {len(timetable)} timetable entries, {len(events_data)} events")
                        # Generate Sessions
                        logger.debug("Generating class sessions...")
                        deterministic_sessions = generate_class_dates(
                            calendar_data["semester_start_date"],
                            calendar_data["semester_end_date"],
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
                                    holidays = get_holidays_from_ai(country, calendar_data["semester_start_date"].year)
                                except Exception as e:
                                    holiday_error = e
                            thread = threading.Thread(target=fetch_holidays)
                            thread.daemon = True
                            thread.start()
                            thread.join(timeout=10)
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
                        filtered_sessions = filter_sessions(deterministic_sessions, events_data, holidays, calendar_data)
                        logger.info(f"{len(filtered_sessions)} sessions remain after filtering")
                        # Clear existing sessions
                        logger.debug("Clearing existing sessions...")
                        existing_sessions = (await session.execute(
                            select(ClassSession).where(ClassSession.teacher_id == teacher_id)
                        )).scalars().all()
                        for session_obj in existing_sessions:
                            await session.delete(session_obj)
                        # Save new sessions
                        logger.debug("Saving new sessions...")
                        for cs in filtered_sessions:
                            session.add(ClassSession(
                                teacher_id=teacher_id,
                                subject=cs["subject"],
                                date=cs["date"],
                                start_time=cs["start_time"],
                                end_time=cs["end_time"],
                                class_name=cs["class_name"],
                                session_number=cs["session_number"],
                                is_completed=False,
                                resource_generated=False,
                                location=cs["location"]
                            ))
                        await asyncio.wait_for(session.commit(), timeout=5.0)
                        logger.info(f"{len(filtered_sessions)} sessions saved to ClassSession")
                    # Populate planner events with a new session
                    logger.debug("Populating planner events...")
                    await populate_teacher_planner_events(teacher_id, calendar_data, events_data, holidays)
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
                except (ClientCannotConnectError, InterfaceError, ConnectionFailureError, asyncio.TimeoutError) as e:
                    await session.rollback()
                    error_msg = f"Connection error in async task: {str(e)}\n{traceback.format_exc()}"
                    logger.error(error_msg)
                    await publish_ws_message(teacher_id, {
                        "status": "error",
                        "message": error_msg,
                        "teacher_id": teacher_id
                    })
                    raise
                except Exception as e:
                    await session.rollback()
                    error_msg = f"Unexpected error in async task: {str(e)}\n{traceback.format_exc()}"
                    logger.error(error_msg)
                    await publish_ws_message(teacher_id, {
                        "status": "error",
                        "message": error_msg,
                        "teacher_id": teacher_id
                    })
                    raise
                finally:
                    await session.close()
                    await conn.close()
    except Exception as e:
        error_msg = f"Task failed: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        # Arq retries are handled in worker config
        raise

# ---------------- ARQ WORKER CONFIG ---------------- #
async def startup(ctx):
    ctx['redis'] = await create_pool(arq_redis_settings)
    logger.info("Arq worker started")

async def shutdown(ctx):
    ctx['redis'].close()
    await ctx['redis'].aclose()
    await async_engine.dispose()
    logger.info("Arq worker shutdown")

worker_config = {
    'functions': [generate_schedule_task],
    'redis_settings': arq_redis_settings,
    'on_startup': startup,
    'on_shutdown': shutdown,
    'max_tries': 5,           # Retry failed jobs 5 times
    'retry_delay': 15,        # Wait 15 seconds between retries
    'job_timeout': 300,       # 5 minutes max per job
    'concurrent_jobs': 2,     # Process 2 jobs simultaneously per worker
    'keep_result': 3600,      # Keep job results for 1 hour
    'max_jobs': 100           # Max jobs to process before worker restart
}

# ---------------- MANUAL RUN (for testing) ---------------- #
if __name__ == "__main__":
    import asyncio
    async def enqueue_task():
        redis = await create_pool(arq_redis_settings)
        try:
            teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
            job = await redis.enqueue_job('generate_schedule_task', teacher_id, "Ghana")
            print("[SUCCESS] Job queued:", job.job_id)
        finally:
            await redis.aclose()
    asyncio.run(enqueue_task())