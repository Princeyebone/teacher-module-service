#!/usr/bin/env python3
"""Test script to debug queue issues"""

import asyncio
import redis
from arq import create_pool
from arq.connections import RedisSettings
from sch_ground.background import arq_redis_settings

async def test_queue():
    print("Testing queue configuration...")
    
    # Create pool with specific queue name
    redis_pool = await create_pool(arq_redis_settings, default_queue_name='schedule_queue')
    print(f"Pool created with default queue: {redis_pool.default_queue_name}")
    
    # Enqueue a job with specific queue
    job = await redis_pool.enqueue_job(
        'generate_schedule_task',
        '7bed2b69-8000-4b36-8e91-7fe0b70c9d82',
        'Ghana',
        _queue_name='schedule_queue'
    )
    print(f"Job enqueued: {job.job_id}")
    
    # Check what's in Redis
    r = redis.Redis(host='localhost', port=6379)
    keys = r.keys('arq:queue*')
    print(f"Queue keys in Redis: {keys}")
    
    # Check the specific queue
    queue_key = 'arq:queue:schedule_queue'
    queue_contents = r.lrange(queue_key, 0, -1)
    print(f"Contents of {queue_key}: {queue_contents}")
    
    await redis_pool.aclose()

if __name__ == "__main__":
    asyncio.run(test_queue())