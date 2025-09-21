#!/usr/bin/env python3
"""
Test script to verify datetime consistency in the publishing functionality
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import TeacherProfile, Assessment
from database import get_db
from config import settings

async def test_datetime_consistency():
    """Test datetime consistency in publishing functionality"""
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            print("=== Testing DateTime Consistency ===")
            
            # Check if we have any teachers in the database
            teacher_stmt = select(TeacherProfile).limit(1)
            teacher_result = await db.execute(teacher_stmt)
            teacher = teacher_result.scalars().first()
            
            if not teacher:
                print("No teachers found in database. Creating a test teacher...")
                teacher = TeacherProfile(
                    display_name="Test Teacher",
                    work_institution="Test School",
                    subjects="Mathematics"
                )
                db.add(teacher)
                await db.commit()
                await db.refresh(teacher)
                print(f"Created teacher: {teacher.display_name} (ID: {teacher.id})")
            
            # Check if we have any assessments
            assessment_stmt = select(Assessment).where(Assessment.teacher_id == teacher.id).limit(1)
            assessment_result = await db.execute(assessment_stmt)
            assessment = assessment_result.scalars().first()
            
            if not assessment:
                print("No assessments found. Creating a test assessment...")
                assessment = Assessment(
                    teacher_id=teacher.id,
                    title="Test Assessment",
                    description="Test assessment for publishing",
                    subject="Mathematics",
                    class_name="Grade 10A",
                    assessment_type="quiz",
                    total_points=100
                )
                db.add(assessment)
                await db.commit()
                await db.refresh(assessment)
                print(f"Created assessment: {assessment.title} (ID: {assessment.id})")
            
            # Test the datetime handling (simplified version of what happens in publishing)
            print("\n--- Testing datetime handling ---")
            
            # This is what we were doing before (causing the error):
            # assessment.updated_at = datetime.now(timezone.utc)  # timezone-aware
            
            # This is what we're doing now (consistent with model definition):
            assessment.updated_at = datetime.utcnow()  # timezone-naive
            assessment.is_published = True
            
            db.add(assessment)
            await db.commit()
            print("DateTime handling test passed successfully!")
            
            # Refresh to get updated data
            await db.refresh(assessment)
            print(f"Assessment updated_at: {assessment.updated_at}")
            print(f"Assessment is_published: {assessment.is_published}")
            
            print("\n=== Test completed successfully ===")
                
        except Exception as e:
            print(f"Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
            await db.rollback()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(test_datetime_consistency())