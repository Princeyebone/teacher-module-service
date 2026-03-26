#!/usr/bin/env python3
"""
Test Script for Timetable Processing

This script tests the new timetable file processing background task.
"""

import asyncio
import os
from pathlib import Path
from app.services.enque_task import enqueue_timetable_processing, check_job_status

async def test_timetable_processing():
    """Test the timetable processing functionality"""
    print("🧪 Testing Timetable File Processing...")
    
    # Test teacher ID
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    
    # Create a test file (you'll need to replace this with an actual file)
    uploads_dir = Path("./uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    # Test with different file types (create dummy files for testing)
    test_files = [
        f"{uploads_dir}/{teacher_id}timetable.pdf",
        f"{uploads_dir}/{teacher_id}timetable.docx", 
        f"{uploads_dir}/{teacher_id}timetable.xlsx"
    ]
    
    print("📝 Creating test files...")
    for test_file in test_files:
        if not os.path.exists(test_file):
            # Create empty test files
            with open(test_file, 'wb') as f:
                f.write(b"Test file content")
            print(f"   Created: {test_file}")
    
    # Test enqueuing jobs
    print("\\n🚀 Enqueuing timetable processing jobs...")
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\\n📄 Processing: {test_file}")
            
            # Enqueue the job
            job_id = await enqueue_timetable_processing(teacher_id, test_file)
            
            if job_id:
                print(f"   ✅ Job enqueued: {job_id}")
                
                # Wait a bit and check status
                await asyncio.sleep(2)
                status = await check_job_status(job_id)
                print(f"   📊 Job status: {status.get('status', 'unknown')}")
                
            else:
                print(f"   ❌ Failed to enqueue job for {test_file}")
    
    print("\\n✨ Test completed!")
    print("\\n📌 To run the worker and process these jobs:")
    print("   python run_timetable_worker.py")
    print("   # OR")
    print("   python -m arq table_back.timetable_worker_config")

if __name__ == "__main__":
    asyncio.run(test_timetable_processing())