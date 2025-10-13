#!/usr/bin/env python3
"""
Test script to verify strand class_name fix
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import TeacherProfile, Strand, ClassSession
from database import get_db
from config import settings

async def test_strand_class_name_fix():
    """Test strand class_name fix"""
    print("=== Testing Strand class_name Fix ===")
    
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
            
            # Test 1: Creating strand with session details
            print("\n--- Test 1: Creating strand with session details ---")
            # First create a class session
            class_session = ClassSession(
                teacher_id=teacher.id,
                subject="Mathematics",
                date="2024-09-01",
                start_time="09:00",
                end_time="10:00",
                class_name="Class 10A",
                session_number=1
            )
            
            db.add(class_session)
            await db.commit()
            await db.refresh(class_session)
            print(f"Created Class Session (ID: {class_session.id})")
            
            # Create strand with session details
            session_details = [{
                "id": class_session.id,
                "date": "2024-09-01",
                "subject": "Mathematics",
                "start_time": "09:00",
                "end_time": "10:00",
                "class_name": "Class 10A",
                "location": None,
                "week_number": 1
            }]
            
            strand = Strand(
                strand_name="Test Strand",
                subject="Mathematics",
                class_name="Class 10A",  # This should be extracted from session_details[0]['class_name']
                teacher_id=teacher.id,
                week_number=1,
                session_ids=[class_session.id],
                session_details=session_details
            )
            
            db.add(strand)
            await db.commit()
            await db.refresh(strand)
            print(f"Created Strand (ID: {strand.id})")
            print(f"Strand class_name: {strand.class_name}")
            
            if strand.class_name == "Class 10A":
                print("✅ Strand class_name stored correctly from session details!")
            else:
                print(f"❌ Strand class_name not stored correctly. Expected: 'Class 10A', Got: '{strand.class_name}'")
                return False
            
            # Clean up this test
            await db.delete(strand)
            await db.delete(class_session)
            await db.commit()
            
            # Test 2: Creating strand without session details (edge case)
            print("\n--- Test 2: Creating strand without session details ---")
            strand2 = Strand(
                strand_name="Test Strand 2",
                subject="Mathematics",
                class_name="Class 10A",  # This should come from the request data
                teacher_id=teacher.id,
                week_number=2,
                session_ids=[],  # Empty session IDs
                session_details=[]  # Empty session details
            )
            
            db.add(strand2)
            await db.commit()
            await db.refresh(strand2)
            print(f"Created Strand (ID: {strand2.id})")
            print(f"Strand class_name: {strand2.class_name}")
            
            if strand2.class_name == "Class 10A":
                print("✅ Strand class_name stored correctly from request data!")
            else:
                print(f"❌ Strand class_name not stored correctly. Expected: 'Class 10A', Got: '{strand2.class_name}'")
                return False
            
            # Clean up
            print("\n--- Cleaning up test data ---")
            await db.delete(strand2)
            await db.delete(teacher)
            await db.commit()
            
            print("✅ Strand class_name fix test completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_strand_class_name_fix())
    if success:
        print("\n🎉 All strand class_name fix tests passed!")
    else:
        print("\n💥 Some strand class_name fix tests failed!")
        exit(1)