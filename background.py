from celery_app import celery_app
from sqlmodel import Session, select
from database import engine
from model import (
    AcademicCalendar, WeeklyTimeTable, CalendarEvent,
    ClassSession, TeacherPlannerEvent, TeacherNotification  # ✅ Added TeacherNotification
)
from datetime import timedelta, date
from external_service import get_holidays_from_ai
import redis
import json
from uuid import UUID
from datetime import datetime

# ---------------- REDIS CLIENT ---------------- #
redis_client = redis.StrictRedis(host="localhost", port=6379, decode_responses=True)


# ---------------- DATABASE UTILS ---------------- #
def get_celery_session():
    return Session(engine)


# ---------------- PUBLISH TO WS + SAVE NOTIFICATION ---------------- #
def save_notification(teacher_id: str, title: str, message: str, type_: str = "info"):
    """Saves notification to TeacherNotification table."""
    session = get_celery_session()
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
        session.commit()
        print(f"✅ Notification saved for teacher {teacher_id}: {title}")
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving notification: {e}")
    finally:
        session.close()


def publish_ws_message(teacher_id: str, message: dict):
    """
    Publish a message to WebSocket via Redis AND save a notification to DB.
    """
    # ✅ Save in DB as notification
    title = "Schedule Update" if message.get("status") != "error" else "Error Occurred"
    save_notification(
        teacher_id=teacher_id,
        title=title,
        message=message.get("message", "Notification"),
        type_="error" if message.get("status") == "error" else "info"
    )

    # ✅ Push to WebSocket via Redis
    try:
        redis_client.publish(f"ws:{teacher_id}", json.dumps(message))
        print(f"📢 [Redis] Published to ws:{teacher_id}: {message}")
    except Exception as e:
        print(f"❌ Redis publish error: {e}")


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
                    "date": current_date.strftime("%Y-%m-%d"),
                    "start_time": entry.start_time.strftime("%H:%M"),
                    "end_time": entry.end_time.strftime("%H:%M"),
                    "class_name": entry.pupils,
                    "location": entry.pupils,
                    "session_number": session_counter
                })
                session_counter += 1
            current_date += timedelta(days=1)
    return sessions


def filter_sessions(sessions, events, holidays, calendar=None):
    """Filters out sessions that fall on holidays, events, breaks, revision period."""
    no_class_dates = set()

    # Mid-Semester Break
    if calendar and calendar.mid_semester_break_start_date and calendar.mid_semester_break_end_date:
        current = calendar.mid_semester_break_start_date
        while current <= calendar.mid_semester_break_end_date:
            no_class_dates.add(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

    # Mid-Semester Exam
    if calendar and calendar.midsem_exams_date:
        no_class_dates.add(calendar.midsem_exams_date.strftime("%Y-%m-%d"))

    # Revision Cutoff
    revision_cutoff = None
    if calendar and calendar.revision_start_date:
        revision_cutoff = calendar.revision_start_date

    # Academic Events
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

    # AI Holidays
    for h in holidays:
        if h.get("requires_no_classes", True):
            no_class_dates.add(h["date"])

    print(f"🚫 No-class dates: {sorted(no_class_dates)}")

    # Filter
    filtered = []
    for s in sessions:
        session_date = date.fromisoformat(s["date"])
        if revision_cutoff and session_date >= revision_cutoff:
            continue
        if s["date"] in no_class_dates:
            continue
        filtered.append(s)
    return filtered


def populate_teacher_planner_events(teacher_id, calendar, events, holidays):
    """Populates TeacherPlannerEvent table with milestones, events & holidays."""
    session = get_celery_session()
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
            existing = session.exec(
                select(TeacherPlannerEvent).where(
                    TeacherPlannerEvent.teacher_id == teacher_id,
                    TeacherPlannerEvent.date == ev["date"],
                    TeacherPlannerEvent.title == ev["title"]
                )
            ).first()

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

        session.commit()
        print(f"✅ {len(all_entries)} events saved/updated in TeacherPlannerEvent.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving TeacherPlannerEvents: {e}")
    finally:
        session.close()


# ---------------- CELERY TASK ---------------- #
@celery_app.task(name="teacher_scheduler.generate_schedule_task")
def generate_schedule_task(teacher_id: str, country: str):
    print(f"🚀 Starting generate_schedule_task for teacher: {teacher_id}")
    
    session = get_celery_session()
    try:
        publish_ws_message(teacher_id, {
            "status": "started",
            "message": "Generating schedule...",
            "teacher_id": teacher_id
        })

        print(f"📋 Fetching calendar for teacher: {teacher_id}")
        calendar = session.exec(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == teacher_id)
        ).first()
        if not calendar:
            error_msg = "No academic calendar found."
            print(f"❌ {error_msg}")
            publish_ws_message(teacher_id, {
                "status": "error",
                "message": error_msg,
                "teacher_id": teacher_id
            })
            return {"error": error_msg}

        print(f"📋 Fetching timetable for teacher: {teacher_id}")
        timetable = session.exec(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == teacher_id)
        ).all()
        if not timetable:
            error_msg = "No timetable found."
            print(f"❌ {error_msg}")
            publish_ws_message(teacher_id, {
                "status": "error",
                "message": error_msg,
                "teacher_id": teacher_id
            })
            return {"error": error_msg}

        print(f"📋 Fetching events for calendar: {calendar.id}")
        events = session.exec(
            select(CalendarEvent).where(CalendarEvent.calender_id == calendar.id)
        ).all()

        print(f"✅ Found: {len(timetable)} timetable entries, {len(events)} events")

    except Exception as e:
        error_msg = f"Error fetching data: {str(e)}"
        print(f"❌ {error_msg}")
        publish_ws_message(teacher_id, {
            "status": "error",
            "message": error_msg,
            "teacher_id": teacher_id
        })
        return {"error": error_msg}
    finally:
        session.close()

    # Generate Sessions
    print("🚀 Generating class sessions...")
    try:
        deterministic_sessions = generate_class_dates(
            calendar.semester_start_date,
            calendar.semester_end_date,
            timetable
        )
        print(f"✅ Generated {len(deterministic_sessions)} sessions before filtering")
    except Exception as e:
        error_msg = f"Error generating sessions: {str(e)}"
        print(f"❌ {error_msg}")
        publish_ws_message(teacher_id, {
            "status": "error",
            "message": error_msg,
            "teacher_id": teacher_id
        })
        return {"error": error_msg}

    # Get holidays with timeout protection
    print(f"🌍 Fetching holidays for {country}...")
    try:
        import threading
        import time
        
        holidays = []
        holiday_error = None
        
        def fetch_holidays():
            nonlocal holidays, holiday_error
            try:
                holidays = get_holidays_from_ai(country, calendar.semester_start_date.year)
            except Exception as e:
                holiday_error = e
        
        # Start holiday fetching in a separate thread with timeout
        thread = threading.Thread(target=fetch_holidays)
        thread.daemon = True
        thread.start()
        thread.join(timeout=30)  # 30 second timeout
        
        if thread.is_alive():
            print("⚠️ Holiday fetch timed out, using empty list")
            holidays = []
        elif holiday_error:
            print(f"⚠️ Error fetching holidays: {holiday_error}, using empty list")
            holidays = []
        else:
            print(f"✅ Fetched {len(holidays)} holidays")
    except Exception as e:
        print(f"⚠️ Error in holiday fetch setup: {e}, using empty list")
        holidays = []

    # Filter sessions
    print("🔍 Filtering sessions...")
    try:
        filtered_sessions = filter_sessions(deterministic_sessions, events, holidays, calendar)
        print(f"✅ {len(filtered_sessions)} sessions remain after filtering")
    except Exception as e:
        error_msg = f"Error filtering sessions: {str(e)}"
        print(f"❌ {error_msg}")
        publish_ws_message(teacher_id, {
            "status": "error",
            "message": error_msg,
            "teacher_id": teacher_id
        })
        return {"error": error_msg}

    # Clear existing sessions for this teacher (optional - uncomment if you want to replace)
    print("🗑️ Clearing existing sessions...")
    clear_session = get_celery_session()
    try:
        existing_sessions = clear_session.exec(
            select(ClassSession).where(ClassSession.teacher_id == teacher_id)
        ).all()
        for session in existing_sessions:
            clear_session.delete(session)
        clear_session.commit()
        print(f"✅ Cleared {len(existing_sessions)} existing sessions")
    except Exception as e:
        print(f"⚠️ Error clearing sessions: {e}")
        clear_session.rollback()
    finally:
        clear_session.close()

    # Save new sessions
    print("💾 Saving new sessions...")
    save_session = get_celery_session()
    try:
        for cs in filtered_sessions:
            save_session.add(ClassSession(
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
        save_session.commit()
        print(f"✅ {len(filtered_sessions)} sessions saved to ClassSession")
    except Exception as e:
        save_session.rollback()
        error_msg = f"Error saving sessions: {str(e)}"
        print(f"❌ {error_msg}")
        publish_ws_message(teacher_id, {
            "status": "error",
            "message": error_msg,
            "teacher_id": teacher_id
        })
        return {"error": error_msg}
    finally:
        save_session.close()

    # Populate planner events
    print("📅 Populating planner events...")
    try:
        populate_teacher_planner_events(teacher_id, calendar, events, holidays)
        print("✅ Planner events populated")
    except Exception as e:
        print(f"⚠️ Error populating planner events: {e}")

    success_msg = f"✅ Schedule generation complete! {len(filtered_sessions)} sessions created"
    print(success_msg)
    publish_ws_message(teacher_id, {
        "status": "completed",
        "message": success_msg,
        "teacher_id": teacher_id,
        "details": {
            "sessions_saved": len(filtered_sessions),
        }
    })

    return {"status": "success", "class_sessions_saved": len(filtered_sessions)}

# ✅ Manual Run (for testing)
if __name__ == "__main__":
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    result = generate_schedule_task.delay(teacher_id, country="Ghana")
    print("✅ Task queued:", result.id)



