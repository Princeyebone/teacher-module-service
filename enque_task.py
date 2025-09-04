"""Task Enqueue Helper for TMDL5 ARQ Worker

This module provides utilities to enqueue background tasks for the TMDL5 system.
Main tasks:
- generate_schedule_task: Creates intelligent class schedules
- process_timetable_file_task: Processes uploaded timetable files with text extraction

Usage:
    from enque_task import enqueue_schedule_generation, enqueue_timetable_processing
    
    # Schedule generation
    job_id = await enqueue_schedule_generation(teacher_id, "Ghana")
    
    # Timetable file processing
    job_id = await enqueue_timetable_processing(teacher_id, file_path)
"""

import asyncio
import logging
from typing import Optional
from arq import create_pool
from sch_ground.background import arq_redis_settings
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


async def enqueue_timetable_processing(teacher_id: str, file_path: str) -> Optional[str]:
    """
    Enqueue a timetable file processing task for a teacher.
    
    Args:
        teacher_id: UUID string of the teacher
        file_path: Path to the uploaded timetable file
        
    Returns:
        Job ID string if successful, None if failed
    """
    try:
        # Validate teacher_id is a valid UUID
        UUID(teacher_id)
        
        redis = await create_pool(arq_redis_settings)
        job = await redis.enqueue_job(
            'process_timetable_file_task', 
            str(teacher_id), 
            file_path
        )
        
        logger.info(f"✅ Timetable processing queued for teacher {teacher_id}: {job.job_id}")
        print(f"📄 Timetable job ID for teacher {teacher_id}: {job.job_id}")
        
        await redis.aclose()
        return job.job_id
        
    except ValueError as e:
        logger.error(f"❌ Invalid teacher_id format: {teacher_id} - {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to enqueue timetable task for {teacher_id}: {e}")
        return None


async def enqueue_schedule_generation(teacher_id: str, country: str = "Ghana") -> Optional[str]:
    """
    Enqueue a schedule generation task for a teacher.
    
    Args:
        teacher_id: UUID string of the teacher
        country: Country for holiday fetching (default: Ghana)
        
    Returns:
        Job ID string if successful, None if failed
    """
    try:
        # Validate teacher_id is a valid UUID
        UUID(teacher_id)
        
        redis = await create_pool(arq_redis_settings)
        job = await redis.enqueue_job(
            'generate_schedule_task', 
            str(teacher_id), 
            country
        )
        
        logger.info(f"✅ Schedule generation queued for teacher {teacher_id}: {job.job_id}")
        print(f"📋 Job ID for teacher {teacher_id}: {job.job_id}")
        
        await redis.aclose()
        return job.job_id
        
    except ValueError as e:
        logger.error(f"❌ Invalid teacher_id format: {teacher_id} - {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to enqueue task for {teacher_id}: {e}")
        return None


async def check_job_status(job_id: str) -> dict:
    """
    Check the status of an ARQ job.
    
    Args:
        job_id: The job ID to check
        
    Returns:
        Dictionary with job status information
    """
    try:
        redis = await create_pool(arq_redis_settings)
        job = await redis.get_job(job_id)
        
        if job is None:
            result = {"status": "not_found", "message": "Job not found"}
        else:
            result = {
                "status": job.status,
                "job_id": job.job_id,
                "function": job.function,
                "enqueued_at": job.enqueued_at,
                "started_at": getattr(job, 'started_at', None),
                "finished_at": getattr(job, 'finished_at', None),
                "result": getattr(job, 'result', None)
            }
            
        await redis.aclose()
        return result
        
    except Exception as e:
        logger.error(f"❌ Error checking job {job_id}: {e}")
        return {"status": "error", "message": str(e)}


async def bulk_enqueue_schedules(teacher_ids: list, country: str = "Ghana") -> dict:
    """
    Enqueue schedule generation for multiple teachers.
    
    Args:
        teacher_ids: List of teacher UUID strings
        country: Country for holiday fetching
        
    Returns:
        Dictionary with success/failure counts and job IDs
    """
    results = {
        "successful": [],
        "failed": [],
        "total": len(teacher_ids)
    }
    
    tasks = [enqueue_schedule_generation(tid, country) for tid in teacher_ids]
    job_ids = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, (teacher_id, job_id) in enumerate(zip(teacher_ids, job_ids)):
        if isinstance(job_id, Exception) or job_id is None:
            results["failed"].append({"teacher_id": teacher_id, "error": str(job_id)})
        else:
            results["successful"].append({"teacher_id": teacher_id, "job_id": job_id})
    
    print(f"📊 Bulk enqueue completed: {len(results['successful'])}/{results['total']} successful")
    return results


# Legacy function for backward compatibility
async def enqueue_task(teacher_id, country="Ghana"):
    """Legacy function - use enqueue_schedule_generation instead"""
    return await enqueue_schedule_generation(str(teacher_id), country)


async def main():
    """Main function for testing task enqueueing"""
    print("🧪 Testing ARQ Task Enqueueing...")
    
    # Test with sample teacher IDs
    test_teacher_ids = [
        "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        # Add more test IDs as needed
    ]
    
    print(f"🎯 Testing with {len(test_teacher_ids)} teacher(s)")
    
    # Test schedule generation
    print("\n📅 Testing Schedule Generation:")
    results = await bulk_enqueue_schedules(test_teacher_ids, "Ghana")
    
    # Print schedule results
    print("\n📋 Schedule Generation Results:")
    for success in results["successful"]:
        print(f"   ✅ {success['teacher_id']}: {success['job_id']}")
    
    for failure in results["failed"]:
        print(f"   ❌ {failure['teacher_id']}: {failure['error']}")
    
    # Test timetable processing
    print("\n📄 Testing Timetable Processing:")
    test_file_path = "./uploads/test_timetable.pdf"
    
    for teacher_id in test_teacher_ids[:1]:  # Test with first teacher only
        timetable_job_id = await enqueue_timetable_processing(teacher_id, test_file_path)
        if timetable_job_id:
            print(f"   ✅ Timetable job for {teacher_id}: {timetable_job_id}")
        else:
            print(f"   ❌ Failed to enqueue timetable job for {teacher_id}")
    
    # Check job status for successful ones
    if results["successful"]:
        print("\n🔍 Checking job statuses...")
        first_job = results["successful"][0]
        status = await check_job_status(first_job["job_id"])
        print(f"   📊 Job {first_job['job_id']}: {status['status']}")


if __name__ == "__main__":
    asyncio.run(main())