from celery_app import celery_app
from sqlmodel import Session, select
from database import engine
from model import (
    AcademicCalendar, WeeklyTimeTable, CalendarEvent,
    ClassSession, TeacherPlannerEvent
)
from datetime import timedelta, date
from external_service import get_holidays_from_ai

def get_celery_session():
    return Session(engine)

WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

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
                    "class_name": entry.subject,
                    "session_number": session_counter
                })
                session_counter += 1
            current_date += timedelta(days=1)
    return sessions

def filter_sessions(sessions, events, holidays, calendar=None):
    """
    Filters out sessions that fall on:
    1. AI-detected holidays
    2. Academic events marked as 'requires_no_classes=True'
    3. Mid-semester break range from calendar
    """
    no_class_dates = set()

    # 1. Mid-Semester Break from calendar
    if calendar and calendar.mid_semester_break_start_date and calendar.mid_semester_break_end_date:
        current = calendar.mid_semester_break_start_date
        while current <= calendar.mid_semester_break_end_date:
            no_class_dates.add(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

    # 2. Academic Events marked as no-class
    for e in events:
        if getattr(e, "requires_no_classes", False):
            start = e.event_start_date
            end = getattr(e, "event_end_date", start)
            if start:
                current = start
                while current <= end:
                    no_class_dates.add(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=1)

    # 3. Holidays from AI
    for h in holidays:
        if h.get("requires_no_classes", True):
            no_class_dates.add(h["date"])

    print(f"🚫 No-class dates (holidays + events + midsem): {sorted(no_class_dates)}")

    return [s for s in sessions if s["date"] not in no_class_dates]

def populate_teacher_planner_events(teacher_id, calendar, events, holidays):
    """
    Populates TeacherPlannerEvent table with:
      - Academic Calendar Milestones
      - Academic Events
      - Holidays
    """
    session = get_celery_session()
    try:
        milestones = [
            {
                "date": calendar.semester_start_date,
                "title": "Semester Begins",
                "description": f"Start of {calendar.semester_name}",
                "event_type": "academic",
                "is_required": True,
            },
            {
                "date": calendar.semester_end_date,
                "title": "Semester Ends",
                "description": f"End of {calendar.semester_name}",
                "event_type": "academic",
                "is_required": True,
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
                })
                current += timedelta(days=1)

        academic_event_entries = []
        for e in events:
            start = e.event_start_date
            end = getattr(e, "event_end_date", start)
            current = start
            while current and current <= end:
                academic_event_entries.append({
                    "date": current,
                    "title": e.event_name or "Academic Event",
                    "description": f"Event: {e.event_name}",
                    "event_type": "academic_event",
                    "is_required": not getattr(e, "requires_no_classes", False),
                })
                current += timedelta(days=1)

        holiday_entries = [
            {
                "date": date.fromisoformat(h["date"]),
                "title": h["name"],
                "description": h.get("description", ""),
                "event_type": "holiday",
                "is_required": not h.get("requires_no_classes", True),
            }
            for h in holidays
        ]

        all_entries = milestones + academic_event_entries + holiday_entries

        for ev in all_entries:
            session.add(TeacherPlannerEvent(
                teacher_id=teacher_id,
                date=ev["date"],
                start_time=None,
                end_time=None,
                title=ev["title"],
                description=ev["description"],
                event_type=ev["event_type"],
                is_required=ev["is_required"]
            ))

        session.commit()
        print(f"✅ {len(all_entries)} events saved to TeacherPlannerEvent.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving TeacherPlannerEvents: {e}")
    finally:
        session.close()

@celery_app.task(name="teacher_scheduler.generate_schedule_task")
def generate_schedule_task(teacher_id: str, country: str = "Ghana"):
    session = get_celery_session()
    try:
        print("✅ Starting Task...")
        print(f"Teacher ID: {teacher_id}")

        calendar = session.exec(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == teacher_id)
        ).first()
        if not calendar:
            return {"error": "No academic calendar found."}

        timetable = session.exec(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == teacher_id)
        ).all()
        if not timetable:
            return {"error": "No timetable found."}

        events = session.exec(
            select(CalendarEvent).where(CalendarEvent.calender_id == calendar.id)
        ).all()

        for e in events:
            print(f"📌 Event: {e.event_name}, {e.event_start_date} → {getattr(e, 'event_end_date', e.event_start_date)}, requires_no_classes={e.requires_no_classes}")

        print(f"✅ Calendar: {calendar.semester_start_date} → {calendar.semester_end_date}")
        print(f"✅ {len(timetable)} timetable entries, {len(events)} academic events.")
    finally:
        session.close()

    # Generate Sessions
    print("🚀 Generating Class Sessions...")
    deterministic_sessions = generate_class_dates(
        calendar.semester_start_date,
        calendar.semester_end_date,
        timetable
    )
    print(f"✅ {len(deterministic_sessions)} sessions before filtering.")

    holidays = get_holidays_from_ai(country, calendar.semester_start_date.year)

    filtered_sessions = filter_sessions(deterministic_sessions, events, holidays, calendar)
    print(f"✅ {len(filtered_sessions)} sessions remain after filtering.")

    save_session = get_celery_session()
    try:
        for cs in filtered_sessions:
            save_session.add(ClassSession(
                teacher_id=teacher_id,
                timetable_id=None,  # Fill with actual timetable.id if needed
                subject=cs["subject"],
                date=cs["date"],
                start_time=cs["start_time"],
                end_time=cs["end_time"],
                class_name=cs["class_name"],
                session_number=cs["session_number"],
                is_completed=False,
                resource_generated=False,
            ))
        save_session.commit()
        print("✅ Sessions saved to DB.")
    except Exception as e:
        save_session.rollback()
        print("❌ Error saving sessions:", e)
        return {"error": str(e)}
    finally:
        save_session.close()

    populate_teacher_planner_events(teacher_id, calendar, events, holidays)

    return {"status": "success", "class_sessions_saved": len(filtered_sessions)}

# ✅ Manual Run
if __name__ == "__main__":
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    result = generate_schedule_task.delay(teacher_id)
    print("✅ Task queued:", result.id)

