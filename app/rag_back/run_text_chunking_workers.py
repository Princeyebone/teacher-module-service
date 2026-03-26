#!/usr/bin/env python3
"""
Runner Script for Text Chunking Workers

This script provides a convenient way to run both text chunking workers
from the root directory of the project.

Usage:
    python run_text_chunking_workers.py [command]
    
Commands:
    start    - Start both text chunking workers (default)
    test     - Test Redis connection
    info     - Show worker configuration
    enqueue  - Enqueue a test task
    
Examples:
    python run_text_chunking_workers.py
    python run_text_chunking_workers.py start
    python run_text_chunking_workers.py info
    python run_text_chunking_workers.py test
"""

import sys
import os
import subprocess
import asyncio
from pathlib import Path

def main():
    """Main function to run the text chunking workers"""
    # Get the command from arguments (default to 'start')
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if command == "start":
        start_both_workers()
    elif command == "test":
        test_redis_connection()
    elif command == "info":
        show_worker_info()
    elif command == "enqueue":
        enqueue_test_task()
    else:
        print("[ERROR] Unknown command. Use: start, test, info, or enqueue")

def start_both_workers():
    """Start both text chunking workers"""
    print("[STARTING] Starting both text chunking workers...")
    
    # Get the paths to the worker scripts
    current_dir = Path(__file__).parent
    worker_1_script = current_dir / "text_chunking_worker_1.py"
    worker_2_script = current_dir / "text_chunking_worker_2.py"
    
    if not worker_1_script.exists():
        print("[ERROR] Text chunking worker 1 script not found!")
        print(f"Expected location: {worker_1_script}")
        sys.exit(1)
        
    if not worker_2_script.exists():
        print("[ERROR] Text chunking worker 2 script not found!")
        print(f"Expected location: {worker_2_script}")
        sys.exit(1)
    
    print(f"[WORKER 1] Starting worker 1: {worker_1_script}")
    print(f"[WORKER 2] Starting worker 2: {worker_2_script}")
    
    try:
        # Start both workers as separate processes
        process_1 = subprocess.Popen([
            sys.executable, str(worker_1_script)
        ])
        
        process_2 = subprocess.Popen([
            sys.executable, str(worker_2_script)
        ])
        
        print("[RUNNING] Both workers are now running. Press Ctrl+C to stop.")
        
        # Wait for both processes
        try:
            process_1.wait()
            process_2.wait()
        except KeyboardInterrupt:
            print("\n[STOPPING] Stopping both workers...")
            process_1.terminate()
            process_2.terminate()
            process_1.wait()
            process_2.wait()
            print("[STOPPED] Both workers stopped.")
            
    except Exception as e:
        print(f"[ERROR] Error running text chunking workers: {e}")
        sys.exit(1)

def test_redis_connection():
    """Test Redis connection"""
    try:
        # Import the Redis settings from the worker module
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.rag_back.text_chunking_worker import text_chunking_redis_settings
        from arq import create_pool
        
        async def test_connection():
            redis = await create_pool(text_chunking_redis_settings)
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
        from app.rag_back.text_chunking_worker import worker_config_1, worker_config_2, text_chunking_redis_settings
        
        print("\n" + "="*60)
        print("[CONFIG] ARQ WORKER CONFIGURATION - TEXT CHUNKING")
        print("="*60)
        print(f"Redis Host: {text_chunking_redis_settings.host}")
        print(f"Redis Port: {text_chunking_redis_settings.port}")
        print(f"Redis Database: {text_chunking_redis_settings.database}")
        print("\n[WORKER 1] Configuration:")
        print(f"   - Queue Name: {worker_config_1['queue_name']}")
        print(f"   - Max Tries: {worker_config_1['max_tries']}")
        print(f"   - Job Timeout: {worker_config_1['job_timeout']} seconds")
        print(f"   - Retry Delay: {worker_config_1['retry_delay']} seconds")
        print(f"   - Concurrent Jobs: {worker_config_1['concurrent_jobs']} per worker")
        print(f"   - Keep Results: {worker_config_1['keep_result']} seconds")
        print("\n[WORKER 2] Configuration:")
        print(f"   - Queue Name: {worker_config_2['queue_name']}")
        print(f"   - Max Tries: {worker_config_2['max_tries']}")
        print(f"   - Job Timeout: {worker_config_2['job_timeout']} seconds")
        print(f"   - Retry Delay: {worker_config_2['retry_delay']} seconds")
        print(f"   - Concurrent Jobs: {worker_config_2['concurrent_jobs']} per worker")
        print(f"   - Keep Results: {worker_config_2['keep_result']} seconds")
        print("\n[TASKS] Registered Tasks:")
        for func in worker_config_1['functions']:
            print(f"   - {func.__name__}")
        print("\n[CAPACITY] WORKER CAPACITY:")
        concurrent_1 = worker_config_1.get('concurrent_jobs', 1)
        concurrent_2 = worker_config_2.get('concurrent_jobs', 1)
        print(f"   - Worker 1 = {concurrent_1} concurrent job(s)")
        print(f"   - Worker 2 = {concurrent_2} concurrent job(s)")
        print(f"   - Total capacity: {concurrent_1 + concurrent_2} concurrent jobs")
        print("="*60)
        
    except Exception as e:
        print(f"[ERROR] Error showing worker info: {e}")
        sys.exit(1)

def enqueue_test_task():
    """Enqueue a test task for debugging"""
    try:
        # Import the Redis settings and enqueue function
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.rag_back.text_chunking_worker import text_chunking_redis_settings
        from arq import create_pool
        
        async def enqueue_task():
            redis = await create_pool(text_chunking_redis_settings)
            try:
                # Example: enqueue text chunking task
                teacher_id = "test-teacher-id"
                file_path = "/path/to/test.pdf"
                gcs_file_name = "test.pdf"
                metadata = {
                    "subject": "Test Subject",
                    "notes": "Test notes",
                    "level": "Test Level",
                    "region": "Test Region",
                    "pillar": "test"
                }
                
                # Enqueue to both queues to test load balancing
                job1 = await redis.enqueue_job(
                    'process_text_chunking_task', 
                    teacher_id, 
                    file_path,
                    gcs_file_name,
                    metadata,
                    _queue_name="text_chunking_queue_1"
                )
                
                job2 = await redis.enqueue_job(
                    'process_text_chunking_task', 
                    teacher_id, 
                    file_path,
                    gcs_file_name,
                    metadata,
                    _queue_name="text_chunking_queue_2"
                )
                
                print(f"[SUCCESS] Test jobs queued:")
                print(f"   - Job 1: {job1.job_id} (queue: text_chunking_queue_1)")
                print(f"   - Job 2: {job2.job_id} (queue: text_chunking_queue_2)")
                return [job1.job_id, job2.job_id]
            finally:
                await redis.aclose()
                
        job_ids = asyncio.run(enqueue_task())
        return job_ids
        
    except Exception as e:
        print(f"[ERROR] Error enqueuing test task: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()