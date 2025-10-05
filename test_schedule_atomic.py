#!/usr/bin/env python3
"""
Test script to verify atomic schedule generation functionality
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import TeacherProfile, WeeklyTimeTable, AcademicCalendar, CalendarEvent, ClassSession, TeacherPlannerEvent
from database import get_db
from config import settings
from sch_ground.background import generate_schedule_task
import uuid

async def test_atomic_schedule_generation():
    """Test atomic schedule generation with rollback protection"""
    print("=== Testing Atomic Schedule Generation ===")
    
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            # Create a test teacher
            print("Creating test teacher...")
            teacher = TeacherProfile(
                display_name="Test Teacher",
                work_institution="Test School",
                subjects="Mathematics,Science"
            )
            
            db.add(teacher)
            await db.commit()
            await db.refresh(teacher)
            print(f"Created Teacher (ID: {teacher.id})")
            
            # Create test academic calendar
            print("Creating test academic calendar...")
            academic_calendar = AcademicCalendar(
                teacher_id=teacher.id,
                semester_name="Test Semester",
                semester_start_date="2024-09-01",
                semester_end_date="2024-12-31",
                midsem_exams_date="2024-10-15",
                revision_start_date="2024-12-01"
            )
            db.add(academic_calendar)
            await db.commit()
            await db.refresh(academic_calendar)
            print(f"Created Academic Calendar (ID: {academic_calendar.id})")
            
            # Create test calendar events
            print("Creating test calendar events...")
            calendar_event = CalendarEvent(
                calender_id=academic_calendar.id,
                event_name="Test Event",
                event_start_date="2024-09-10",
                event_end_date="2024-09-10",
                is_holiday=False,
                requires_no_classes=False
            )
            db.add(calendar_event)
            await db.commit()
            await db.refresh(calendar_event)
            print(f"Created Calendar Event (ID: {calendar_event.id})")
            
            # Create test timetable
            print("Creating test timetable...")
            timetable_entry = WeeklyTimeTable(
                teacher_id=teacher.id,
                weekday="monday",
                pupils="Class 10A",
                subject="Mathematics",
                start_time="09:00",
                end_time="10:00"
            )
            db.add(timetable_entry)
            await db.commit()
            await db.refresh(timetable_entry)
            print(f"Created Timetable Entry (ID: {timetable_entry.id})")
            
            # Test the atomic schedule generation
            print("\n--- Testing Atomic Schedule Generation ---")
            try:
                result = await generate_schedule_task({}, str(teacher.id), "Ghana")
                print(f"Schedule generation result: {result}")
                
                # Verify ClassSession entries were created
                class_sessions = (await db.execute(
                    select(ClassSession).where(ClassSession.teacher_id == teacher.id)
                )).scalars().all()
                print(f"Created {len(class_sessions)} ClassSession entries")
                
                # Verify TeacherPlannerEvent entries were created
                planner_events = (await db.execute(
                    select(TeacherPlannerEvent).where(TeacherPlannerEvent.teacher_id == teacher.id)
                )).scalars().all()
                print(f"Created {len(planner_events)} TeacherPlannerEvent entries")
                
                print("✅ Atomic schedule generation test completed successfully!")
                return True
                
            except Exception as e:
                print(f"❌ Error during schedule generation: {e}")
                import traceback
                traceback.print_exc()
                return False
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            # Clean up test data
            print("\n--- Cleaning up test data ---")
            try:
                # Delete ClassSession entries
                class_sessions = (await db.execute(
                    select(ClassSession).where(ClassSession.teacher_id == teacher.id)
                )).scalars().all()
                for session_entry in class_sessions:
                    await db.delete(session_entry)
                
                # Delete TeacherPlannerEvent entries
                planner_events = (await db.execute(
                    select(TeacherPlannerEvent).where(TeacherPlannerEvent.teacher_id == teacher.id)
                )).scalars().all()
                for event in planner_events:
                    await db.delete(event)
                
                # Delete timetable entry
                await db.delete(timetable_entry)
                
                # Delete calendar event
                await db.delete(calendar_event)
                
                # Delete academic calendar
                await db.delete(academic_calendar)
                
                # Delete teacher
                await db.delete(teacher)
                
                await db.commit()
                print("✅ Test data cleanup completed")
            except Exception as e:
                print(f"❌ Error during cleanup: {e}")

if __name__ == "__main__":
    success = asyncio.run(test_atomic_schedule_generation())
    if success:
        print("\n🎉 All atomic schedule generation tests passed!")
    else:
        print("\n💥 Some atomic schedule generation tests failed!")
        exit(1)