"""
ARQ Worker Configuration for TMDL5 Teacher Management System

This file provides the proper ARQ worker configuration and startup scripts.
ARQ (Async Redis Queue) is used instead of traditional Celery for better
async/await support with FastAPI.

Usage:
    # Start ARQ worker
    python -m arq background.worker_config
    
    # Or run this file directly
    python arq_worker.py
    
    # Or use the convenience function
    from arq_worker import start_worker
    await start_worker()
"""

import asyncio
import sys
from pathlib import Path
from arq import create_pool
from arq.worker import run_worker
import nest_asyncio  # Add this import to handle nested event loops

try:
    from .background import worker_config, arq_redis_settings
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    # Add both current directory and parent directory to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)
    sys.path.insert(0, current_dir)
    from background import worker_config, arq_redis_settings


async def start_worker():
    """Start the ARQ worker programmatically"""
    print("[STARTING] ARQ Worker for TMDL5...")
    print("[TASKS] Available tasks:")
    for func in worker_config['functions']:
        print(f"   - {func.__name__}")
    
    # Run the worker
    await run_worker(worker_config)


async def test_connection():
    """Test Redis connection"""
    try:
        redis = await create_pool(arq_redis_settings)
        await redis.ping()
        print("[SUCCESS] Redis connection successful")
        await redis.aclose()
        return True
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        return False


async def enqueue_test_task():
    """Enqueue a test task for debugging"""
    redis = await create_pool(arq_redis_settings)
    try:
        # Example: enqueue schedule generation task
        teacher_id = "test-teacher-id"
        country = "Ghana"
        
        job = await redis.enqueue_job(
            'generate_schedule_task', 
            teacher_id, 
            country
        )
        print(f"[SUCCESS] Test job queued: {job.job_id}")
        return job.job_id
    finally:
        await redis.aclose()


def print_worker_info():
    """Print worker configuration information"""
    print("\n" + "="*50)
    print("[CONFIG] ARQ WORKER CONFIGURATION")
    print("="*50)
    print(f"Redis Host: {arq_redis_settings.host}")
    print(f"Redis Port: {arq_redis_settings.port}")
    print(f"Redis Queue Name: schedule_queue")
    print(f"Max Tries: {worker_config.get('max_tries', 'default')}")
    print(f"Job Timeout: {worker_config.get('job_timeout', 'default')} seconds")
    print(f"Retry Delay: {worker_config.get('retry_delay', 'default')} seconds")
    print(f"Concurrent Jobs: {worker_config.get('concurrent_jobs', 1)} per worker")
    print(f"Keep Results: {worker_config.get('keep_result', 'default')} seconds")
    print("\n[TASKS] Registered Tasks:")
    for func in worker_config['functions']:
        print(f"   - {func.__name__}")
    print("\n[CAPACITY] WORKER CAPACITY:")
    concurrent = worker_config.get('concurrent_jobs', 1)
    print(f"   - 1 Worker Process = {concurrent} concurrent job(s)")
    print(f"   - Recommended for production: 3-5 worker processes")
    print(f"   - Total capacity with 3 workers: {concurrent * 3} concurrent jobs")
    print("="*50)


def run_worker_safely():
    """Run worker with proper event loop handling"""
    try:
        # Apply nest_asyncio to allow nested event loops
        nest_asyncio.apply()
        print_worker_info()
        asyncio.run(start_worker())
    except RuntimeError as e:
        if "already running" in str(e):
            # If event loop is already running, run the worker directly
            print("[INFO] Event loop already running, using alternative startup method")
            import uvloop
            if sys.platform != 'win32':
                uvloop.install()
            # Create a new event loop and run the worker
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_worker())
        else:
            raise


if __name__ == "__main__":
    """
    Command line interface for ARQ worker management
    
    Usage:
        python arq_worker.py [command]
        
    Commands:
        start    - Start the worker (default)
        test     - Test Redis connection
        info     - Show configuration info
        enqueue  - Enqueue a test task
    """
    
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if command == "start":
        run_worker_safely()
    elif command == "test":
        asyncio.run(test_connection())
    elif command == "info":
        print_worker_info()
    elif command == "enqueue":
        asyncio.run(enqueue_test_task())
    else:
        print("[ERROR] Unknown command. Use: start, test, info, or enqueue")