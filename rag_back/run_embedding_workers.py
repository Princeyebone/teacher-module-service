#!/usr/bin/env python3
"""
Runner Script for Embedding Workers

This script provides a convenient way to run the embedding worker
from the root directory of the project.

Usage:
    python run_embedding_workers.py [command]
    
Commands:
    start    - Start the embedding worker (default)
    test     - Test Redis connection
    info     - Show worker configuration
    enqueue  - Enqueue a test task
    
Examples:
    python run_embedding_workers.py
    python run_embedding_workers.py start
    python run_embedding_workers.py info
    python run_embedding_workers.py test
"""

import sys
import os
import subprocess
import asyncio
from pathlib import Path

def main():
    """Main function to run the embedding worker"""
    # Get the command from arguments (default to 'start')
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if command == "start":
        start_embedding_worker()
    elif command == "test":
        test_redis_connection()
    elif command == "info":
        show_worker_info()
    elif command == "enqueue":
        enqueue_test_task()
    else:
        print("[ERROR] Unknown command. Use: start, test, info, or enqueue")

def start_embedding_worker():
    """Start the embedding worker"""
    print("[STARTING] Starting embedding worker...")
    
    # Get the path to the worker script
    current_dir = Path(__file__).parent
    worker_script = current_dir / "embedding_worker.py"
    
    if not worker_script.exists():
        print("[ERROR] Embedding worker script not found!")
        print(f"Expected location: {worker_script}")
        sys.exit(1)
    
    print(f"[WORKER] Starting worker: {worker_script}")
    
    try:
        # Start the worker as a separate process
        process = subprocess.Popen([
            sys.executable, str(worker_script)
        ])
        
        print("[RUNNING] Embedding worker is now running. Press Ctrl+C to stop.")
        
        # Wait for the process
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n[STOPPING] Stopping embedding worker...")
            process.terminate()
            process.wait()
            print("[STOPPED] Embedding worker stopped.")
            
    except Exception as e:
        print(f"[ERROR] Error running embedding worker: {e}")
        sys.exit(1)

def test_redis_connection():
    """Test Redis connection"""
    try:
        # Import the Redis settings from the worker module
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rag_back.embedding_worker import embedding_redis_settings
        from arq import create_pool
        
        async def test_connection():
            redis = await create_pool(embedding_redis_settings)
            await redis.ping()
            print("[SUCCESS] Redis connection successful")
            await redis.aclose()
            return True
            
        asyncio.run(test_connection())
        
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        sys.exit(1)

def show_worker_info():
    """Show worker configuration information"""
    try:
        # Import the worker configurations
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rag_back.embedding_worker import worker_config, embedding_redis_settings
        
        print("\n" + "="*60)
        print("[CONFIG] ARQ WORKER CONFIGURATION - EMBEDDING GENERATION")
        print("="*60)
        print(f"Redis Host: {embedding_redis_settings.host}")
        print(f"Redis Port: {embedding_redis_settings.port}")
        print(f"Redis Database: {embedding_redis_settings.database}")
        print("\n[WORKER] Configuration:")
        print(f"   - Queue Name: {worker_config['queue_name']}")
        print(f"   - Max Tries: {worker_config['max_tries']}")
        print(f"   - Job Timeout: {worker_config['job_timeout']} seconds")
        print(f"   - Retry Delay: {worker_config['retry_delay']} seconds")
        print(f"   - Concurrent Jobs: {worker_config['concurrent_jobs']} per worker")
        print(f"   - Keep Results: {worker_config['keep_result']} seconds")
        print("\n[TASKS] Registered Tasks:")
        for func in worker_config['functions']:
            print(f"   - {func.__name__}")
        print("\n[CAPACITY] WORKER CAPACITY:")
        concurrent = worker_config.get('concurrent_jobs', 1)
        print(f"   - Worker = {concurrent} concurrent job(s)")
        print("="*60)
        
    except Exception as e:
        print(f"[ERROR] Error showing worker info: {e}")
        sys.exit(1)

def enqueue_test_task():
    """Enqueue a test task for debugging"""
    try:
        # Import the Redis settings and enqueue function
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rag_back.embedding_worker import embedding_redis_settings
        from arq import create_pool
        
        async def enqueue_task():
            redis = await create_pool(embedding_redis_settings)
            try:
                # Example: enqueue embedding task
                teacher_id = "test-teacher-id"
                knowledge_id = 1
                chunks = ["This is a test chunk for embedding generation."] * 5
                metadata = {
                    "subject": "Test Subject",
                    "notes": "Test notes"
                }
                
                # Enqueue to the single queue
                job = await redis.enqueue_job(
                    'process_embedding_task', 
                    teacher_id, 
                    knowledge_id,
                    chunks,
                    metadata,
                    _queue_name="embedding_queue"
                )
                
                print(f"[SUCCESS] Test job queued:")
                print(f"   - Job: {job.job_id} (queue: embedding_queue)")
                return job.job_id
            finally:
                await redis.aclose()
                
        job_id = asyncio.run(enqueue_task())
        return job_id
        
    except Exception as e:
        print(f"[ERROR] Error enqueuing test task: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()