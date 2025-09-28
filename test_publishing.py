#!/usr/bin/env python3
"""
Test script to verify publishing functionality
"""
import asyncio
from datetime import datetime  # Added datetime import
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import TeacherProfile, Assessment, AssessmentAssignment, SecuritySetting, StudentAccessRule
from database import get_db
from config import settings

async def test_publishing():
    """Test publishing functionality"""
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            print("=== Testing Publishing Functionality ===")
            
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
            
            # Test the publishing logic (simplified version)
            print("\n--- Testing publishing logic ---")
            
            # Update the assessment to be published
            assessment.is_published = True
            assessment.updated_at = assessment.updated_at  # This will be updated by the database
            db.add(assessment)
            
            # Create the assignment
            assignment = AssessmentAssignment(
                assessment_id=assessment.id,
                assigned_by_teacher_id=teacher.id,
                available_from=assessment.updated_at,
                available_until=assessment.updated_at,
                time_limit_minutes=60,
                max_attempts=3,
                is_active=True,
                show_results_timing="after_submission"
            )
            
            db.add(assignment)
            await db.flush()  # Flush to get the assignment ID
            print(f"Created assignment (ID: {assignment.id})")
            
            # Create security settings
            security_setting = SecuritySetting(
                assignment_id=assignment.id,
                strict_mode=True,
                open_mode=False,
                free_mode=False,
                review=False,  # Added review field
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(security_setting)
            print("Created security settings")
            
            # Create access rules
            access_rule = StudentAccessRule(
                assignment_id=assignment.id,
                student_id=None,
                class_id=None,
                can_access=True
            )
            
            db.add(access_rule)
            print("Created access rules")
            
            # Commit the transaction
            await db.commit()
            print("Committed transaction successfully")
            
            # Refresh objects to get updated data
            await db.refresh(assessment)
            await db.refresh(assignment)
            print("Refreshed objects successfully")
            
            print("\n=== Test completed successfully ===")
                
        except Exception as e:
            print(f"Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
            await db.rollback()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(test_publishing())