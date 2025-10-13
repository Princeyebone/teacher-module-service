#!/usr/bin/env python3
"""Test script to debug worker queue configuration"""

import asyncio
from arq import create_pool, run_worker
from arq.connections import RedisSettings
from sch_ground.background import generate_schedule_task

# Create Redis settings
redis_settings = RedisSettings(host="localhost", port=6379)

# Worker configuration
worker_config = {
    'functions': [generate_schedule_task],
    'redis_settings': redis_settings,
    'queue_name': 'schedule_queue',  # Try without arq:queue: prefix
    'max_tries': 5,
    'job_timeout': 300,
    'concurrent_jobs': 2,
    'keep_result': 3600,
    'max_jobs': 100
}

async def main():
    print("Starting worker with config:", worker_config)
    await run_worker(worker_config)

if __name__ == "__main__":
    asyncio.run(main())