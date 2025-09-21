"""
Test script to demonstrate the student deletion endpoint
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel, select
from sqlalchemy import delete
from model import Student, TeacherProfile
from student_auth import create_student
from config import settings
from uuid import uuid4

async def test_delete_student():
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
        
        print(f"Created test teacher: {teacher.email}")
        
        # Create a test student
        student_data = {
            "teacher_id": teacher.id,
            "email": "student@test.com",
            "index_number": "STU001",
            "name": "Test Student",
            "student_id": 1,
            "class_name": "Class A"
        }
        
        student = await create_student(student_data, session)
        print(f"Created test student: {student.email} with ID: {student.id}")
        
        # Verify student exists
        statement = select(Student).where(Student.id == student.id)
        result = await session.execute(statement)
        existing_student = result.scalar_one_or_none()
        assert existing_student is not None, "Student should exist"
        print(f"Verified student exists: {existing_student.email}")
        
        # Test deletion (simulating the endpoint logic)
        # In a real scenario, this would be done through the API endpoint
        await session.delete(existing_student)
        await session.commit()
        print(f"Deleted student with ID: {student.id}")
        
        # Verify student is deleted
        statement = select(Student).where(Student.id == student.id)
        result = await session.execute(statement)
        deleted_student = result.scalar_one_or_none()
        assert deleted_student is None, "Student should be deleted"
        print("Verified student deletion successful")
        
        print("All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_delete_student())