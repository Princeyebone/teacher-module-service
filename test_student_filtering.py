#!/usr/bin/env python3
"""
Test script to verify student filtering functionality
"""
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from model import Student, StudentEnrollment, TeacherProfile
from database import get_db
from config import settings

async def test_student_filtering():
    """Test student filtering functionality"""
    # Create database session
    async_engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            print("=== Testing Student Filtering Functionality ===")
            
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
            
            # Create test students
            print("\n--- Creating test students ---")
            students_data = [
                {
                    "name": "Alice Johnson",
                    "email": "alice@example.com",
                    "index_number": "ALICE001",
                    "class_name": "Grade 10A"
                },
                {
                    "name": "Bob Smith",
                    "email": "bob@example.com",
                    "index_number": "BOB001",
                    "class_name": "Grade 10A"
                },
                {
                    "name": "Charlie Brown",
                    "email": "charlie@example.com",
                    "index_number": "CHARLIE001",
                    "class_name": "Grade 10B"
                },
                {
                    "name": "Diana Prince",
                    "email": "diana@example.com",
                    "index_number": "DIANA001",
                    "class_name": "Grade 10B"
                }
            ]
            
            students = []
            for student_data in students_data:
                student = Student(
                    teacher_id=teacher.id,
                    class_name=student_data["class_name"],
                    email=student_data["email"],
                    index_number=student_data["index_number"],
                    hashed_password="hashed_password",
                    name=student_data["name"],
                    password_changed=False
                )
                db.add(student)
                students.append(student)
            
            await db.commit()
            
            # Refresh all students
            for student in students:
                await db.refresh(student)
            
            print(f"Created {len(students)} students")
            
            # Create enrollments
            print("\n--- Creating enrollments ---")
            enrollments_data = [
                {
                    "student": students[0],
                    "subject": "Mathematics",
                    "class_name": "Grade 10A"
                },
                {
                    "student": students[1],
                    "subject": "Mathematics",
                    "class_name": "Grade 10A"
                },
                {
                    "student": students[2],
                    "subject": "Science",
                    "class_name": "Grade 10B"
                },
                {
                    "student": students[3],
                    "subject": "Science",
                    "class_name": "Grade 10B"
                },
                {
                    "student": students[0],  # Alice also enrolled in Science
                    "subject": "Science",
                    "class_name": "Grade 10A"
                }
            ]
            
            enrollments = []
            for enrollment_data in enrollments_data:
                enrollment = StudentEnrollment(
                    student_id=enrollment_data["student"].id,
                    subject=enrollment_data["subject"],
                    class_name=enrollment_data["class_name"],
                    teacher_display_name=teacher.display_name,
                    is_active=True
                )
                db.add(enrollment)
                enrollments.append(enrollment)
            
            await db.commit()
            
            # Refresh all enrollments
            for enrollment in enrollments:
                await db.refresh(enrollment)
            
            print(f"Created {len(enrollments)} enrollments")
            
            # Test filtering by class_name
            print("\n--- Testing filtering by class_name ---")
            grade_10a_query = select(Student).join(StudentEnrollment).where(
                StudentEnrollment.teacher_display_name == teacher.display_name,
                StudentEnrollment.class_name == "Grade 10A"
            ).distinct()
            
            grade_10a_result = await db.execute(grade_10a_query)
            grade_10a_students = grade_10a_result.scalars().all()
            print(f"Students in Grade 10A: {len(grade_10a_students)}")
            for student in grade_10a_students:
                print(f"  - {student.name}")
            
            grade_10b_query = select(Student).join(StudentEnrollment).where(
                StudentEnrollment.teacher_display_name == teacher.display_name,
                StudentEnrollment.class_name == "Grade 10B"
            ).distinct()
            
            grade_10b_result = await db.execute(grade_10b_query)
            grade_10b_students = grade_10b_result.scalars().all()
            print(f"Students in Grade 10B: {len(grade_10b_students)}")
            for student in grade_10b_students:
                print(f"  - {student.name}")
            
            # Test filtering by subject
            print("\n--- Testing filtering by subject ---")
            math_query = select(Student).join(StudentEnrollment).where(
                StudentEnrollment.teacher_display_name == teacher.display_name,
                StudentEnrollment.subject == "Mathematics"
            ).distinct()
            
            math_result = await db.execute(math_query)
            math_students = math_result.scalars().all()
            print(f"Students in Mathematics: {len(math_students)}")
            for student in math_students:
                print(f"  - {student.name}")
            
            science_query = select(Student).join(StudentEnrollment).where(
                StudentEnrollment.teacher_display_name == teacher.display_name,
                StudentEnrollment.subject == "Science"
            ).distinct()
            
            science_result = await db.execute(science_query)
            science_students = science_result.scalars().all()
            print(f"Students in Science: {len(science_students)}")
            for student in science_students:
                print(f"  - {student.name}")
            
            # Test combined filtering
            print("\n--- Testing combined filtering ---")
            combined_query = select(Student).join(StudentEnrollment).where(
                StudentEnrollment.teacher_display_name == teacher.display_name,
                StudentEnrollment.class_name == "Grade 10A",
                StudentEnrollment.subject == "Mathematics"
            ).distinct()
            
            combined_result = await db.execute(combined_query)
            combined_students = combined_result.scalars().all()
            print(f"Students in Grade 10A taking Mathematics: {len(combined_students)}")
            for student in combined_students:
                print(f"  - {student.name}")
            
            print("\n=== Test completed successfully ===")
                
        except Exception as e:
            print(f"Error during test: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(test_student_filtering())