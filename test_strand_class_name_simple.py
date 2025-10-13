#!/usr/bin/env python3
"""
Test script to verify simplified strand class_name functionality
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import TeacherProfile, Strand
from database import get_db
from config import settings

async def test_strand_class_name_simple():
    """Test simplified strand class_name functionality"""
    print("=== Testing Simplified Strand class_name Functionality ===")
    
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
            
            # Test creating strand with class_name from payload
            print("\n--- Testing Strand Creation with class_name from payload ---")
            strand = Strand(
                strand_name="Test Strand",
                subject="Mathematics",
                class_name="Class 10A",  # Directly from payload
                teacher_id=teacher.id,
                week_number=1,
                session_ids=[],
                session_details=[]
            )
            
            db.add(strand)
            await db.commit()
            await db.refresh(strand)
            print(f"Created Strand (ID: {strand.id})")
            print(f"Strand class_name: {strand.class_name}")
            
            # Verify class_name is stored correctly
            if strand.class_name == "Class 10A":
                print("✅ Strand class_name stored correctly from payload!")
            else:
                print(f"❌ Strand class_name not stored correctly. Expected: 'Class 10A', Got: '{strand.class_name}'")
                return False
            
            # Update the strand with session details
            print("\n--- Testing Strand Update with session details ---")
            strand.class_name = "Class 10B"  # Update from payload
            strand.session_ids = [1, 2, 3]
            strand.session_details = [
                {
                    "id": 1,
                    "date": "2024-09-01",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10B",  # This could be different but we're using payload value
                    "location": None,
                    "week_number": 1
                }
            ]
            strand.updated_at = strand.updated_at  # This will be updated automatically
            
            await db.commit()
            await db.refresh(strand)
            print(f"Updated Strand class_name: {strand.class_name}")
            
            if strand.class_name == "Class 10B":
                print("✅ Strand class_name updated correctly from payload!")
            else:
                print(f"❌ Strand class_name not updated correctly. Expected: 'Class 10B', Got: '{strand.class_name}'")
                return False
            
            # Clean up
            print("\n--- Cleaning up test data ---")
            await db.delete(strand)
            await db.delete(teacher)
            await db.commit()
            
            print("✅ Simplified strand class_name test completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_strand_class_name_simple())
    if success:
        print("\n🎉 All simplified strand class_name tests passed!")
    else:
        print("\n💥 Some simplified strand class_name tests failed!")
        exit(1)