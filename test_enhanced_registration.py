"""
Test script to demonstrate the enhanced student registration flow with automatic enrollment
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel, select
from model import Student, TeacherProfile, StudentEnrollment
from student_auth import create_student
from config import settings
from uuid import uuid4

async def test_enhanced_registration():
    # Create test database engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async with async_session() as session:
        # Create a test teacher with subject and class information
        teacher = TeacherProfile(
            id=uuid4(),
            email="teacher@test.com",
            name="Test Teacher",
            subjects="Mathematics",
            work_institution="Class A"
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        
        print(f"Created test teacher: {teacher.id} with subject: {teacher.subjects}")
        
        # Create a test student with enrollment information
        student_data = {
            "teacher_id": teacher.id,
            "email": "student@test.com",
            "index_number": "STU001",
            "name": "Test Student",
            "class_name": teacher.work_institution,
            "teacher_subject": teacher.subjects,
            "teacher_class_name": teacher.work_institution
        }
        
        student = await create_student(student_data, session)
        print(f"Created test student: {student.email} with ID: {student.id}")
        
        # Verify student exists
        statement = select(Student).where(Student.id == student.id)
        result = await session.execute(statement)
        existing_student = result.scalar_one_or_none()
        assert existing_student is not None, "Student should exist"
        print(f"Verified student exists: {existing_student.email}")
        
        # Verify enrollment was created
        enrollment_statement = select(StudentEnrollment).where(StudentEnrollment.student_id == student.id)
        enrollment_result = await session.execute(enrollment_statement)
        enrollment = enrollment_result.scalar_one_or_none()
        assert enrollment is not None, "Enrollment should exist"
        print(f"Verified enrollment exists for subject: {enrollment.subject} and class: {enrollment.class_name}")
        
        print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_enhanced_registration())