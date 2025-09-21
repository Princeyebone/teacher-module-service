#!/usr/bin/env python3
"""
Test script to verify student deletion functionality
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select, delete
from model import Student, StudentEnrollment
from database import get_db
from config import settings

async def test_student_deletion():
    """Test student deletion functionality"""
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            # Create a test student
            print("Creating test student...")
            test_student = Student(
                teacher_id=uuid.uuid4(),  # Random teacher ID
                class_name="Test Class",
                email="test@example.com",
                index_number="TEST001",
                hashed_password="hashed_password",
                name="Test Student",
                password_changed=False
            )
            
            db.add(test_student)
            await db.commit()
            await db.refresh(test_student)
            
            print(f"Created test student with ID: {test_student.id}")
            
            # Create a test enrollment
            print("Creating test enrollment...")
            test_enrollment = StudentEnrollment(
                student_id=test_student.id,
                subject="Test Subject",
                class_name="Test Class",
                teacher_display_name="Test Teacher",
                is_active=True
            )
            
            db.add(test_enrollment)
            await db.commit()
            await db.refresh(test_enrollment)
            
            print(f"Created test enrollment with ID: {test_enrollment.id}")
            
            # Verify the student and enrollment exist
            student_stmt = select(Student).where(Student.id == test_student.id)
            student_result = await db.execute(student_stmt)
            student = student_result.scalar_one_or_none()
            
            enrollment_stmt = select(StudentEnrollment).where(StudentEnrollment.student_id == test_student.id)
            enrollment_result = await db.execute(enrollment_stmt)
            enrollments = enrollment_result.scalars().all()
            
            print(f"Verification - Student exists: {student is not None}")
            print(f"Verification - Enrollments found: {len(enrollments)}")
            
            # Test deletion process (manual cascade)
            print("Testing deletion process...")
            
            # Delete associated enrollments first
            enrollment_delete_stmt = delete(StudentEnrollment).where(StudentEnrollment.student_id == test_student.id)
            await db.execute(enrollment_delete_stmt)
            await db.commit()
            print("Deleted associated enrollments")
            
            # Delete the student
            student_delete_stmt = delete(Student).where(Student.id == test_student.id)
            await db.execute(student_delete_stmt)
            await db.commit()
            print("Deleted student")
            
            # Verify deletion
            student_stmt = select(Student).where(Student.id == test_student.id)
            student_result = await db.execute(student_stmt)
            student = student_result.scalar_one_or_none()
            
            enrollment_stmt = select(StudentEnrollment).where(StudentEnrollment.student_id == test_student.id)
            enrollment_result = await db.execute(enrollment_stmt)
            enrollments = enrollment_result.scalars().all()
            
            print(f"Post-deletion - Student exists: {student is not None}")
            print(f"Post-deletion - Enrollments found: {len(enrollments)}")
            
            if student is None and len(enrollments) == 0:
                print("SUCCESS: Student deletion test passed")
            else:
                print("FAILURE: Student deletion test failed")
                
        except Exception as e:
            print(f"Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(test_student_deletion())