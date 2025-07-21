#background.py
from celery_app import celery_app
from sqlmodel import Session, select
from database import engine  # Ensure engine is imported correctly
from model import AcademicCalendar, WeeklyTimeTable, CalendarEvent
from external_service import call_gemini_schedule  # Gemini AI call


def get_celery_session():
    return Session(engine)


@celery_app.task(name="teacher_scheduler.generate_schedule_task")
def generate_schedule_task(teacher_id: str, country: str = "Ghana"):
    """Fetch timetable + academic calendar + events, call AI, and return JSON."""
    session = get_celery_session()
    try:
        # ✅ 1. Fetch Academic Calendar
        calendar = session.exec(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == teacher_id)
        ).first()
        if not calendar:
            return {"error": "No academic calendar found."}

        # ✅ 2. Fetch Timetable
        timetable = session.exec(
            select(WeeklyTimeTable).where(WeeklyTimeTable.teacher_id == teacher_id)
        ).all()
        if not timetable:
            return {"error": "No timetable found for this teacher"}

        # ✅ 3. Fetch Calendar Events
        events = session.exec(
            select(CalendarEvent).where(CalendarEvent.calender_id == calendar.id)
        ).all()

    finally:
        session.close()

    # ✅ 4. Call AI (Gemini)
    class_sessions, planner_events = call_gemini_schedule(calendar, timetable, events, country)

    return {
        "status": "success",
        "class_sessions": class_sessions,
        "planner_events": planner_events
    }


# ✅ Only run this manually when executing `python background.py`
if __name__ == "__main__":
    result = generate_schedule_task.delay("teacher-uuid-here")
    print("Task Queued:", result.id)
    print(result.get())
