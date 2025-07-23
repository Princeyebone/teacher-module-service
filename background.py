from celery_app import celery_app
from sqlmodel import Session, select, delete
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
                    "session_number": session_counter,
                    "location": entry.location
                })
                session_counter += 1
            current_date += timedelta(days=1)
    return sessions


def filter_sessions(sessions, events, holidays, calendar=None):
    """
    Filters out sessions that fall on:
    1. AI-detected holidays
    2. Academic events marked as 'requires no class'
    3. Mid-semester break range from calendar
    4. Mid-semester exam date
    5. Any date on or after revision_start_date
    """
    no_class_dates = set()

    # ✅ Mid-Semester Break
    if calendar and calendar.mid_semester_break_start_date and calendar.mid_semester_break_end_date:
        current = calendar.mid_semester_break_start_date
        while current <= calendar.mid_semester_break_end_date:
            no_class_dates.add(current)
            current += timedelta(days=1)

    # ✅ Mid-Semester Exam Date
    if calendar and calendar.midsem_exams_date:
        no_class_dates.add(calendar.midsem_exams_date)

    # ✅ Academic Events marked as no-class
    for e in events:
        requires_no_classes = getattr(e, "requires_no_classes", False)
        if requires_no_classes:
            start = e.event_start_date
            end = getattr(e, "event_end_date", start)
            if start:
                current = start
                while current <= end:
                    no_class_dates.add(current)
                    current += timedelta(days=1)

    # ✅ Holidays from AI
    for h in holidays:
        if h.get("requires_no_classes", True):
            no_class_dates.add(date.fromisoformat(h["date"]))

    # ✅ Revision Cutoff
    revision_cutoff = None
    if calendar and calendar.revision_start_date:
        revision_cutoff = calendar.revision_start_date

    print(f"🚫 No-class dates: {[d.strftime('%Y-%m-%d') for d in sorted(no_class_dates)]}")
    if revision_cutoff:
        print(f"🚫 Revision cutoff: {revision_cutoff}")

    filtered = []
    for s in sessions:
        session_date = date.fromisoformat(s["date"])
        if session_date in no_class_dates:
            continue
        if revision_cutoff and session_date >= revision_cutoff:
            continue
        filtered.append(s)

    return filtered


def populate_teacher_planner_events(teacher_id, calendar, events, holidays):
    """Populates TeacherPlannerEvent with academic calendar, events, and holidays."""
    session = get_celery_session()
    try:
        # ✅ Delete old entries for this teacher
        session.exec(delete(TeacherPlannerEvent).where(TeacherPlannerEvent.teacher_id == teacher_id))
        session.commit()

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

        # ✅ Mid-Semester Exam
        if calendar.midsem_exams_date:
            milestones.append({
                "date": calendar.midsem_exams_date,
                "title": "Mid-Semester Exam",
                "description": "No classes (mid-semester exam)",
                "event_type": "exam",
                "is_required": False,
                "start_time": None,
                "end_time": None
            })

        # ✅ Revision Period
        if calendar.revision_start_date:
            milestones.append({
                "date": calendar.revision_start_date,
                "title": "Revision Period Begins",
                "description": "Start of revision period - no classes",
                "event_type": "revision",
                "is_required": False,
                "start_time": None,
                "end_time": None
            })

        # ✅ Mid-Semester Break
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

        # ✅ Academic Events (NOW WITH TIME)
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
                    "is_required": not e.requires_no_classes,
                    "start_time": e.event_start_time.strftime("%H:%M") if e.event_start_time else None,
                    "end_time": e.event_end_time.strftime("%H:%M") if e.event_end_time else None
                })
                current += timedelta(days=1)

        # ✅ AI Holidays
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
        print(f"✅ {len(all_entries)} events saved to TeacherPlannerEvent.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving TeacherPlannerEvents: {e}")
    finally:
        session.close()


@celery_app.task(name="teacher_scheduler.generate_schedule_task")
def generate_schedule_task(teacher_id: str, country: str):
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

        print(f"✅ Calendar: {calendar.semester_start_date} → {calendar.semester_end_date}")
        print(f"✅ {len(timetable)} timetable entries, {len(events)} academic events.")
    finally:
        session.close()

    # ✅ Generate Sessions
    print("🚀 Generating Class Sessions...")
    deterministic_sessions = generate_class_dates(
        calendar.semester_start_date,
        calendar.semester_end_date,
        timetable
    )
    print(f"✅ {len(deterministic_sessions)} sessions before filtering.")

    # ✅ AI Holidays
    holidays = get_holidays_from_ai(country, calendar.semester_start_date.year)

    # ✅ Filter Sessions
    filtered_sessions = filter_sessions(deterministic_sessions, events, holidays, calendar)
    print(f"✅ {len(filtered_sessions)} sessions remain after filtering.")

    # ✅ Clear Old ClassSessions Before Saving
    save_session = get_celery_session()
    try:
        save_session.exec(delete(ClassSession).where(ClassSession.teacher_id == teacher_id))
        save_session.commit()

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
        print("✅ Sessions saved to DB.")
    except Exception as e:
        save_session.rollback()
        print("❌ Error saving sessions:", e)
        return {"error": str(e)}
    finally:
        save_session.close()

    # ✅ Save Planner Events
    populate_teacher_planner_events(teacher_id, calendar, events, holidays)

    return {"status": "success", "class_sessions_saved": len(filtered_sessions)}

# ✅ Manual Run
if __name__ == "__main__":
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    result = generate_schedule_task.delay(teacher_id, "Ghana")
    print("✅ Task queued:", result.id)


