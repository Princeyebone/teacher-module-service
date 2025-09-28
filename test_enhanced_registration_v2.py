"""
Test script to demonstrate the enhanced student registration flow with frontend-provided class_name and subject
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel, select
from model import Student, TeacherProfile, StudentEnrollment
from student_auth import create_student
from config import settings
from uuid import uuid4

async def test_enhanced_registration_v2():
    # Create test database engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async with async_session() as session:
        # Create a test teacher
        teacher = TeacherProfile(
            id=uuid4(),
            email="teacher@test.com",
            name="Test Teacher"
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        
        print(f"Created test teacher: {teacher.id}")
        
        # Test 1: Create a student with specific class_name and subject
        student_data = {
            "teacher_id": teacher.id,
            "email": "student1@test.com",
            "index_number": "STU001",
            "name": "Test Student 1",
            "class_name": "Advanced Mathematics Class",
            "subject": "Advanced Mathematics"
        }
        
        student1 = await create_student(student_data, session)
        print(f"Created test student: {student1.email} with ID: {student1.id}")
        
        # Verify student exists
        statement = select(Student).where(Student.id == student1.id)
        result = await session.execute(statement)
        existing_student = result.scalar_one_or_none()
        assert existing_student is not None, "Student should exist"
        print(f"Verified student exists: {existing_student.email}")
        print(f"Student created successfully: {existing_student.email}")
        
        # Verify enrollment was created
        enrollment_statement = select(StudentEnrollment).where(StudentEnrollment.student_id == student1.id)
        enrollment_result = await session.execute(enrollment_statement)
        enrollment = enrollment_result.scalar_one_or_none()
        assert enrollment is not None, "Enrollment should exist"
        print(f"Verified enrollment exists for subject: {enrollment.subject} and class: {enrollment.class_name}")
        
        # Test 2: Create a student without subject (no enrollment should be created)
        student_data2 = {
            "teacher_id": teacher.id,
            "email": "student2@test.com",
            "index_number": "STU002",
            "name": "Test Student 2",
            "class_name": "General Studies Class"
            # No subject provided
        }
        
        student2 = await create_student(student_data2, session)
        print(f"Created test student without subject: {student2.email} with ID: {student2.id}")
        
        # Verify student exists
        statement2 = select(Student).where(Student.id == student2.id)
        result2 = await session.execute(statement2)
        existing_student2 = result2.scalar_one_or_none()
        assert existing_student2 is not None, "Student should exist"
        print(f"Verified student exists: {existing_student2.email}")
        print(f"Student created successfully: {existing_student2.email}")
        
        # Verify no enrollment was created
        enrollment_statement2 = select(StudentEnrollment).where(StudentEnrollment.student_id == student2.id)
        enrollment_result2 = await session.execute(enrollment_statement2)
        enrollment2 = enrollment_result2.scalar_one_or_none()
        assert enrollment2 is None, "No enrollment should exist when no subject is provided"
        print("Verified no enrollment was created when no subject was provided")
        
        print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_enhanced_registration_v2())