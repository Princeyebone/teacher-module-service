#!/usr/bin/env python3
"""Test script to debug Redis pool configuration"""

import asyncio
from arq import create_pool
from app.sch_ground.background import arq_redis_settings

async def test_redis_pool():
    print("Testing Redis pool configuration...")
    
    # Create pool with specific queue name
    redis_pool = await create_pool(arq_redis_settings, default_queue_name='schedule_queue')
    print(f"Pool created")
    print(f"Pool type: {type(redis_pool)}")
    print(f"Has default_queue_name attr: {hasattr(redis_pool, 'default_queue_name')}")
    
    if hasattr(redis_pool, 'default_queue_name'):
        print(f"Default queue name: {redis_pool.default_queue_name}")
    
    # Try to get queue name through other means
    print(f"Pool attributes: {[attr for attr in dir(redis_pool) if 'queue' in attr.lower()]}")
    
    await redis_pool.aclose()

if __name__ == "__main__":
    asyncio.run(test_redis_pool())