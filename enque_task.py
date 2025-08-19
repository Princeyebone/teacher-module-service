import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from uuid import uuid4

async def enqueue_task(teacher_id, country="Ghana"):
    redis = await create_pool(RedisSettings(host='localhost', port=6379))
    try:
        job = await redis.enqueue_job('generate_schedule_task', str(teacher_id), country)
        print(f"Job ID for {teacher_id}: {job.job_id}")
    finally:
        await redis.aclose()

async def main():
    # Generate 10 valid UUIDs for testing
    teacher_ids = ["7bed2b69-8000-4b36-8e91-7fe0b70c9d82"]
    tasks = [enqueue_task(teacher_id) for teacher_id in teacher_ids]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())