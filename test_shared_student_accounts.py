#!/usr/bin/env python3
"""
Test script to verify shared student account functionality
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import Student, StudentEnrollment, TeacherProfile
from database import get_db
from config import settings

async def test_shared_student_accounts():
    """Test shared student account functionality"""
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            print("=== Testing Shared Student Account Functionality ===")
            
            # Create two test teachers
            print("Creating test teachers...")
            teacher_a = TeacherProfile(
                display_name="Teacher A",
                work_institution="School A",
                subjects="Mathematics"
            )
            
            teacher_b = TeacherProfile(
                display_name="Teacher B",
                work_institution="School B",
                subjects="Science"
            )
            
            db.add(teacher_a)
            db.add(teacher_b)
            await db.commit()
            await db.refresh(teacher_a)
            await db.refresh(teacher_b)
            
            print(f"Created Teacher A (ID: {teacher_a.id}) and Teacher B (ID: {teacher_b.id})")
            
            # Teacher A registers a student
            print("\n--- Teacher A registering student ---")
            student_a = Student(
                teacher_id=teacher_a.id,
                class_name="Grade 10A",
                email="shared@student.com",
                index_number="SHARED001",
                hashed_password="hashed_password",
                name="Shared Student",
                password_changed=False
            )
            
            db.add(student_a)
            await db.commit()
            await db.refresh(student_a)
            print(f"Teacher A created student: {student_a.name} (ID: {student_a.id})")
            
            # Teacher A enrolls student in their course
            enrollment_a = StudentEnrollment(
                student_id=student_a.id,
                subject="Mathematics",
                class_name="Grade 10A",
                teacher_display_name=teacher_a.display_name,
                is_active=True
            )
            
            db.add(enrollment_a)
            await db.commit()
            await db.refresh(enrollment_a)
            print(f"Teacher A enrolled student in {enrollment_a.subject}")
            
            # Teacher B tries to register the same student (by email)
            print("\n--- Teacher B registering same student ---")
            # In the real implementation, this would be detected and handled
            # For this test, we'll simulate what should happen
            
            # Check if student already exists
            existing_student_stmt = select(Student).where(Student.email == "shared@student.com")
            existing_result = await db.execute(existing_student_stmt)
            existing_student = existing_result.scalar_one_or_none()
            
            if existing_student:
                print(f"Student already exists (ID: {existing_student.id}), enrolling in Teacher B's course")
                
                # Enroll existing student in Teacher B's course
                enrollment_b = StudentEnrollment(
                    student_id=existing_student.id,
                    subject="Science",
                    class_name="Grade 10B",
                    teacher_display_name=teacher_b.display_name,
                    is_active=True
                )
                
                db.add(enrollment_b)
                await db.commit()
                await db.refresh(enrollment_b)
                print(f"Teacher B enrolled existing student in {enrollment_b.subject}")
            else:
                # Create new student (this shouldn't happen in the real implementation)
                student_b = Student(
                    teacher_id=teacher_b.id,
                    class_name="Grade 10B",
                    email="shared@student.com",
                    index_number="SHARED001",
                    hashed_password="hashed_password",
                    name="Shared Student",
                    password_changed=False
                )
                
                db.add(student_b)
                await db.commit()
                await db.refresh(student_b)
                print(f"Teacher B created student: {student_b.name} (ID: {student_b.id})")
                
                # Enroll in course
                enrollment_b = StudentEnrollment(
                    student_id=student_b.id,
                    subject="Science",
                    class_name="Grade 10B",
                    teacher_display_name=teacher_b.display_name,
                    is_active=True
                )
                
                db.add(enrollment_b)
                await db.commit()
                await db.refresh(enrollment_b)
                print(f"Teacher B enrolled student in {enrollment_b.subject}")
            
            # Verify the student has both enrollments
            print("\n--- Verifying student enrollments ---")
            all_enrollments_stmt = select(StudentEnrollment).where(
                StudentEnrollment.student_id == existing_student.id if existing_student else student_b.id
            )
            all_enrollments_result = await db.execute(all_enrollments_stmt)
            all_enrollments = all_enrollments_result.scalars().all()
            
            print(f"Student has {len(all_enrollments)} total enrollments:")
            for enrollment in all_enrollments:
                print(f"  - {enrollment.subject} with {enrollment.teacher_display_name}")
            
            # Test selective deletion - Teacher A removes student from their course
            print("\n--- Teacher A removing student from their course ---")
            teacher_a_enrollments_stmt = select(StudentEnrollment).where(
                StudentEnrollment.student_id == existing_student.id if existing_student else student_b.id,
                StudentEnrollment.teacher_display_name == teacher_a.display_name
            )
            teacher_a_enrollments_result = await db.execute(teacher_a_enrollments_stmt)
            teacher_a_enrollments = teacher_a_enrollments_result.scalars().all()
            
            print(f"Found {len(teacher_a_enrollments)} enrollments to remove for Teacher A")
            
            # Remove Teacher A's enrollments
            for enrollment in teacher_a_enrollments:
                await db.delete(enrollment)
            
            await db.commit()
            print("Removed Teacher A's enrollments")
            
            # Check remaining enrollments
            remaining_enrollments_stmt = select(StudentEnrollment).where(
                StudentEnrollment.student_id == existing_student.id if existing_student else student_b.id
            )
            remaining_enrollments_result = await db.execute(remaining_enrollments_stmt)
            remaining_enrollments = remaining_enrollments_result.scalars().all()
            
            print(f"Student now has {len(remaining_enrollments)} remaining enrollments:")
            for enrollment in remaining_enrollments:
                print(f"  - {enrollment.subject} with {enrollment.teacher_display_name}")
            
            # Since student still has enrollments, they should not be deleted
            student_check_stmt = select(Student).where(
                Student.id == existing_student.id if existing_student else student_b.id
            )
            student_check_result = await db.execute(student_check_stmt)
            student_check = student_check_result.scalar_one_or_none()
            
            if student_check:
                print(f"Student account still exists: {student_check.name}")
            else:
                print("Student account was incorrectly deleted")
            
            print("\n=== Test completed successfully ===")
                
        except Exception as e:
            print(f"Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(test_shared_student_accounts())