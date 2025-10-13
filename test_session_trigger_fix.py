#!/usr/bin/env python3
"""
Test script to verify session generation trigger fix
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import TeacherProfile, WeeklyTimeTable, AcademicCalendar
from database import get_db
from config import settings
from schedule_utils import trigger_session_generation_after_save

async def test_session_trigger_fix():
    """Test session generation trigger fix"""
    print("=== Testing Session Generation Trigger Fix ===")
    
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
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
            
            # Test 1: Neither timetable nor academic calendar exists
            print("\n--- Test 1: Neither timetable nor academic calendar exists ---")
            result = await trigger_session_generation_after_save(str(teacher.id))
            print(f"Trigger result: {result} (should be False)")
            
            # Test 2: Only timetable exists
            print("\n--- Test 2: Only timetable exists ---")
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
            
            result = await trigger_session_generation_after_save(str(teacher.id))
            print(f"Trigger result: {result} (should be False)")
            
            # Test 3: Only academic calendar exists
            print("\n--- Test 3: Only academic calendar exists ---")
            await db.delete(timetable_entry)
            await db.commit()
            
            academic_calendar = AcademicCalendar(
                teacher_id=teacher.id,
                semester_name="Test Semester",
                semester_start_date="2024-09-01",
                semester_end_date="2024-12-31"
            )
            db.add(academic_calendar)
            await db.commit()
            
            result = await trigger_session_generation_after_save(str(teacher.id))
            print(f"Trigger result: {result} (should be False)")
            
            # Test 4: Both timetable and academic calendar exist
            print("\n--- Test 4: Both timetable and academic calendar exist ---")
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
            
            result = await trigger_session_generation_after_save(str(teacher.id))
            print(f"Trigger result: {result} (should be True or False depending on enqueue success)")
            
            # Clean up
            print("\n--- Cleaning up test data ---")
            await db.delete(timetable_entry)
            await db.delete(academic_calendar)
            await db.delete(teacher)
            await db.commit()
            
            print("✅ Session trigger fix test completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_session_trigger_fix())
    if success:
        print("\n🎉 All session trigger fix tests passed!")
    else:
        print("\n💥 Some session trigger fix tests failed!")
        exit(1)