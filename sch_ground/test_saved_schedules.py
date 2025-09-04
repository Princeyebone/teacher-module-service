from sqlmodel import Session, select
from database import engine
from model import ClassSession, TeacherPlannerEvent
from uuid import UUID

def check_saved_schedules(teacher_id: str):
    with Session(engine) as session:
        sessions = session.exec(
            select(ClassSession).where(ClassSession.teacher_id == UUID(teacher_id))
        ).all()
        events = session.exec(
            select(TeacherPlannerEvent).where(TeacherPlannerEvent.teacher_id == UUID(teacher_id))
        ).all()

        print(f"\n✅ Found {len(sessions)} Class Sessions for teacher {teacher_id}:")
        for s in sessions[:5]:  # show only first 5
            print(f" - {s.date} | {s.subject} | {s.start_time}-{s.end_time}")

        print(f"\n✅ Found {len(events)} Planner Events:")
        for e in events[:5]:
            print(f" - {e.date} | {e.title} | {e.start_time}-{e.end_time}")

if __name__ == "__main__":
    check_saved_schedules("7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
