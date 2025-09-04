#!/usr/bin/env python3
"""
Test Script for UploadedFile Database Integration

This script demonstrates how the timetable processing system
integrates with the UploadedFile database table.
"""

import asyncio
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

# Import necessary models and utilities
from sch_ground.background import async_engine
from model import UploadedFile, TeacherProfile
from enque_task import enqueue_timetable_processing, check_job_status

async def get_teacher_uploaded_files(teacher_id: str, purpose: str = "timetable"):
    """Get all uploaded files for a teacher"""
    print(f"🔍 Fetching uploaded files for teacher {teacher_id}...")
    
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(UploadedFile)
            .where(UploadedFile.teacher_id == UUID(teacher_id))
            .where(UploadedFile.purpose == purpose)
            .order_by(UploadedFile.id.desc())
        )
        files = result.scalars().all()
        
        print(f"📁 Found {len(files)} uploaded files:")
        for file in files:
            print(f"   📄 {file.file_name} ({file.file_type}) - ID: {file.id}")
            print(f"      Extracted text length: {len(file.extracted_text) if file.extracted_text else 0} characters")
            print(f"      GCS Path: {file.gcs_path or 'Not set'}")
        
        return files

async def get_uploaded_file_by_id(file_id: str):
    """Get specific file by ID"""
    print(f"🔍 Fetching file with ID: {file_id}")
    
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(UploadedFile)
            .where(UploadedFile.id == UUID(file_id))
        )
        file = result.scalar_one_or_none()
        
        if file:
            print(f"✅ Found file: {file.file_name}")
            print(f"   Teacher ID: {file.teacher_id}")
            print(f"   File Type: {file.file_type}")
            print(f"   Purpose: {file.purpose}")
            print(f"   Extracted Text Preview: {file.extracted_text[:100] if file.extracted_text else 'None'}...")
        else:
            print("❌ File not found")
        
        return file

async def test_database_integration():
    """Test the database integration with file processing"""
    print("🧪 Testing UploadedFile Database Integration...\n")
    
    # Test teacher ID
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    
    # Create test uploads directory
    uploads_dir = Path("./uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # Create a simple test file
    test_file = f"{uploads_dir}/{teacher_id}timetable.txt"
    test_content = """
    Monday 9:00-10:00 Mathematics Class 5A
    Tuesday 11:00-12:00 Science Class 5B
    Wednesday 8:00-9:00 English Class 5A
    """
    
    if not os.path.exists(test_file):
        with open(test_file, 'w') as f:
            f.write(test_content)
        print(f"📝 Created test file: {test_file}")
    
    # Check existing files first
    print("🔍 Checking existing uploaded files...")
    existing_files = await get_teacher_uploaded_files(teacher_id)
    
    # Enqueue a new processing job
    print(f"\n🚀 Enqueuing timetable processing job...")
    job_id = await enqueue_timetable_processing(teacher_id, test_file)
    
    if job_id:
        print(f"✅ Job enqueued: {job_id}")
        
        # Wait a bit and check status
        print("⏳ Waiting for job to process...")
        await asyncio.sleep(3)
        
        status = await check_job_status(job_id)
        print(f"📊 Job status: {status.get('status', 'unknown')}")
        
        # Check if new file record was created
        print("\n🔍 Checking for new uploaded files...")
        new_files = await get_teacher_uploaded_files(teacher_id)
        
        if len(new_files) > len(existing_files):
            latest_file = new_files[0]  # Most recent first
            print(f"\n🎉 New file record created!")
            await get_uploaded_file_by_id(str(latest_file.id))
        
    else:
        print("❌ Failed to enqueue job")
    
    print("\n✨ Database integration test completed!")
    print("\n📌 Notes:")
    print("   - File records are automatically created during background processing")
    print("   - gcs_path is left blank as requested")
    print("   - extracted_text contains the full text extracted from the file")
    print("   - purpose is set to 'timetable' for this system")

async def cleanup_test_files():
    """Clean up test files"""
    print("🧹 Cleaning up test files...")
    
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    test_file = f"./uploads/{teacher_id}timetable.txt"
    
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"🗑️ Removed: {test_file}")

if __name__ == "__main__":
    try:
        asyncio.run(test_database_integration())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
    finally:
        # Uncomment to clean up test files
        # asyncio.run(cleanup_test_files())
        pass