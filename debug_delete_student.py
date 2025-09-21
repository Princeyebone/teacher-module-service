#!/usr/bin/env python3
"""
Debug script to test student deletion
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import Student, StudentEnrollment, TeacherProfile
from database import get_db
from config import settings

async def debug_student_deletion(student_id_str: str, teacher_id_str: str = None):
    """Debug student deletion by checking what's in the database"""
    # Convert string to UUID
    student_id = uuid.UUID(student_id_str)
    
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            print(f"Debugging student deletion for ID: {student_id}")
            
            # Check if student exists
            statement = select(Student).where(Student.id == student_id)
            result = await db.execute(statement)
            student = result.scalar_one_or_none()
            
            if student:
                print(f"Student found:")
                print(f"  ID: {student.id}")
                print(f"  Name: {student.name}")
                print(f"  Email: {student.email}")
                print(f"  Index Number: {student.index_number}")
                print(f"  Teacher ID: {student.teacher_id}")
                print(f"  Created At: {student.created_at}")
                
                # Check if teacher exists
                if teacher_id_str:
                    teacher_id = uuid.UUID(teacher_id_str)
                    teacher_stmt = select(TeacherProfile).where(TeacherProfile.id == teacher_id)
                    teacher_result = await db.execute(teacher_stmt)
                    teacher = teacher_result.scalar_one_or_none()
                    
                    if teacher:
                        print(f"Teacher found:")
                        print(f"  ID: {teacher.id}")
                        print(f"  Display Name: {teacher.display_name}")
                        print(f"  Match: {student.teacher_id == teacher.id}")
                    else:
                        print(f"No teacher found with ID: {teacher_id}")
                
            else:
                print(f"No student found with ID: {student_id}")
                return
            
            # Check associated enrollments
            enrollment_statement = select(StudentEnrollment).where(StudentEnrollment.student_id == student_id)
            enrollment_result = await db.execute(enrollment_statement)
            enrollments = enrollment_result.scalars().all()
            
            print(f"Found {len(enrollments)} associated enrollments:")
            for enrollment in enrollments:
                print(f"  Enrollment ID: {enrollment.id}")
                print(f"    Subject: {enrollment.subject}")
                print(f"    Class Name: {enrollment.class_name}")
                print(f"    Created At: {enrollment.created_at}")
                
        except Exception as e:
            print(f"Error during debug: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python debug_delete_student.py <student_id> [teacher_id]")
        sys.exit(1)
    
    student_id = sys.argv[1]
    teacher_id = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(debug_student_deletion(student_id, teacher_id))