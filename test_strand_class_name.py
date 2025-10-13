#!/usr/bin/env python3
"""
Test script to verify strand class_name functionality
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import TeacherProfile, Strand, ClassSession
from database import get_db
from config import settings

async def test_strand_class_name():
    """Test strand class_name functionality"""
    print("=== Testing Strand class_name Functionality ===")
    
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
            
            # Create test class session
            print("Creating test class session...")
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
            
            # Test creating strand with class_name
            print("\n--- Testing Strand Creation with class_name ---")
            strand = Strand(
                strand_name="Test Strand",
                subject="Mathematics",
                class_name="Class 10A",
                teacher_id=teacher.id,
                week_number=1,
                session_ids=[class_session.id],
                session_details=[{
                    "id": class_session.id,
                    "date": "2024-09-01",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": None,
                    "week_number": 1
                }]
            )
            
            db.add(strand)
            await db.commit()
            await db.refresh(strand)
            print(f"Created Strand (ID: {strand.id})")
            print(f"Strand class_name: {strand.class_name}")
            
            # Verify class_name is stored correctly
            if strand.class_name == "Class 10A":
                print("✅ Strand class_name stored correctly!")
            else:
                print(f"❌ Strand class_name not stored correctly. Expected: 'Class 10A', Got: '{strand.class_name}'")
                return False
            
            # Clean up
            print("\n--- Cleaning up test data ---")
            await db.delete(strand)
            await db.delete(class_session)
            await db.delete(teacher)
            await db.commit()
            
            print("✅ Strand class_name test completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_strand_class_name())
    if success:
        print("\n🎉 All strand class_name tests passed!")
    else:
        print("\n💥 Some strand class_name tests failed!")
        exit(1)