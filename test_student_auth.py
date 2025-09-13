"""
Test script to demonstrate the student authentication system
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from model import Student
from student_auth import get_password_hash, create_student_tokens, authenticate_student
from config import settings

async def test_student_auth():
    # Create test database engine
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async with async_session() as session:
        # Create a test student
        test_student_data = {
            "email": "student@test.com",
            "password": "securepassword123",
            "index_number": "STU001",
            "name": "Test Student"
        }
        
        # Hash password
        hashed_password = get_password_hash(test_student_data["password"])
        
        # Create student object
        student = Student(
            email=test_student_data["email"],
            index_number=test_student_data["index_number"],
            hashed_password=hashed_password,
            name=test_student_data["name"]
        )
        
        # Add to database
        session.add(student)
        await session.commit()
        await session.refresh(student)
        
        print(f"Created test student: {student.email}")
        
        # Test authentication
        authenticated_student = await authenticate_student(
            test_student_data["email"], 
            test_student_data["password"], 
            session
        )
        
        if authenticated_student:
            print(f"Authentication successful for: {authenticated_student.email}")
            
            # Create tokens
            tokens = create_student_tokens(authenticated_student)
            print(f"Access Token: {tokens['access_token']}")
            print(f"Refresh Token: {tokens['refresh_token']}")
        else:
            print("Authentication failed")
        
        # Test failed authentication
        failed_auth = await authenticate_student(
            test_student_data["email"], 
            "wrongpassword", 
            session
        )
        
        if failed_auth:
            print("ERROR: Authentication should have failed but didn't")
        else:
            print("Correctly failed authentication with wrong password")

if __name__ == "__main__":
    asyncio.run(test_student_auth())