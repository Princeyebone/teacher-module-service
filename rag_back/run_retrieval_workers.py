#!/usr/bin/env python3
"""
Runner Script for Retrieval Workers

This script starts multiple retrieval workers for parallel query processing.
Configured for 3 workers by default.

Usage:
    python run_retrieval_workers.py [command] [num_workers]
    
Commands:
    start    - Start the retrieval workers (default)
    test     - Test Redis connection
    info     - Show worker configuration
    enqueue  - Enqueue a test task
    
Examples:
    python run_retrieval_workers.py                 # Start 3 workers (default)
    python run_retrieval_workers.py start 5         # Start 5 workers
    python run_retrieval_workers.py info
    python run_retrieval_workers.py test
"""

import sys
import os
import subprocess
import asyncio
import signal
import time
from pathlib import Path
from typing import List

# Default number of workers
DEFAULT_NUM_WORKERS = 3


def main():
    """Main function to run the retrieval workers"""
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    num_workers = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_NUM_WORKERS
    
    if command == "start":
        start_retrieval_workers(num_workers)
    elif command == "test":
        test_redis_connection()
    elif command == "info":
        show_worker_info()
    elif command == "enqueue":
        enqueue_test_task()
    else:
        print("[ERROR] Unknown command. Use: start, test, info, or enqueue")
        sys.exit(1)


def start_retrieval_workers(num_workers: int = DEFAULT_NUM_WORKERS):
    """Start multiple retrieval workers"""
    print("=" * 60)
    print(f"[STARTING] Starting {num_workers} Retrieval Worker(s)...")
    print("=" * 60)
    
    # Get the path to the worker script
    current_dir = Path(__file__).parent
    worker_script = current_dir / "retrieval_worker.py"
    
    if not worker_script.exists():
        print(f"[ERROR] Retrieval worker script not found!")
        print(f"Expected location: {worker_script}")
        sys.exit(1)
    
    processes: List[subprocess.Popen] = []
    
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully"""
        print("\n" + "=" * 60)
        print("[STOPPING] Shutting down all workers...")
        print("=" * 60)
        for i, proc in enumerate(processes):
            if proc.poll() is None:  # Process is still running
                print(f"   Stopping worker {i + 1}...")
                proc.terminate()
        
        # Wait for all processes to terminate
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        
        print("[STOPPED] All workers stopped.")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start each worker
        for i in range(num_workers):
            log_file = current_dir.parent / f"retrieval_worker_{i + 1}.log"
            
            print(f"[WORKER {i + 1}] Starting worker...")
            print(f"   Script: {worker_script}")
            print(f"   Log: {log_file}")
            
            # Open log file for writing
            log_handle = open(log_file, 'a')
            
            # Start the worker process
            process = subprocess.Popen(
                [sys.executable, str(worker_script)],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                cwd=str(current_dir.parent)
            )
            processes.append(process)
            print(f"   PID: {process.pid}")
            print(f"   ✅ Worker {i + 1} started successfully")
            
            # Small delay between starting workers
            time.sleep(0.5)
        
        print("=" * 60)
        print(f"[RUNNING] {num_workers} retrieval worker(s) are now running.")
        print(f"   Total concurrent jobs: {num_workers * 3}")  # 3 jobs per worker
        print("   Press Ctrl+C to stop all workers.")
        print("=" * 60)
        
        # Monitor workers
        while True:
            time.sleep(5)
            
            # Check if any worker has died
            for i, proc in enumerate(processes):
                if proc.poll() is not None:
                    print(f"[WARNING] Worker {i + 1} (PID {proc.pid}) has stopped. Restarting...")
                    
                    # Restart the worker
                    log_file = current_dir.parent / f"retrieval_worker_{i + 1}.log"
                    log_handle = open(log_file, 'a')
                    
                    new_process = subprocess.Popen(
                        [sys.executable, str(worker_script)],
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        cwd=str(current_dir.parent)
                    )
                    processes[i] = new_process
                    print(f"   ✅ Worker {i + 1} restarted with PID {new_process.pid}")
                    
    except Exception as e:
        print(f"[ERROR] Error running workers: {e}")
        signal_handler(None, None)


def test_redis_connection():
    """Test Redis connection"""
    print("[TEST] Testing Redis connection...")
    
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rag_back.retrieval_worker import retrieval_redis_settings
        from arq import create_pool
        
        async def test_connection():
            redis = await create_pool(retrieval_redis_settings)
            await redis.ping()
            print("[SUCCESS] ✅ Redis connection successful")
            print(f"   Host: {retrieval_redis_settings.host}")
            print(f"   Port: {retrieval_redis_settings.port}")
            print(f"   Database: {retrieval_redis_settings.database}")
            await redis.aclose()
            return True
            
        asyncio.run(test_connection())
        
    except Exception as e:
        print(f"[ERROR] ❌ Redis connection failed: {e}")
        sys.exit(1)


def show_worker_info():
    """Show worker configuration information"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rag_back.retrieval_worker import worker_config, retrieval_redis_settings
        
        print("\n" + "=" * 60)
        print("[CONFIG] ARQ WORKER CONFIGURATION - RETRIEVAL")
        print("=" * 60)
        print(f"Redis Host: {retrieval_redis_settings.host}")
        print(f"Redis Port: {retrieval_redis_settings.port}")
        print(f"Redis Database: {retrieval_redis_settings.database}")
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
        print("\n[CAPACITY] With 3 Workers:")
        concurrent = worker_config.get('concurrent_jobs', 1)
        print(f"   - Total concurrent jobs: {concurrent * 3}")
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] Error showing worker info: {e}")
        sys.exit(1)


def enqueue_test_task():
    """Enqueue a test retrieval task"""
    print("[TEST] Enqueueing test retrieval task...")
    
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rag_back.retrieval_worker import retrieval_redis_settings
        from arq import create_pool
        
        async def enqueue_task():
            redis = await create_pool(retrieval_redis_settings)
            try:
                # Example: enqueue retrieval task
                test_params = {
                    'teacher_id': "test-teacher-id",
                    'query': "What are the learning objectives for fractions?",
                    'subject': "Mathematics",
                    'pillar': "curriculum",
                    'class_level': "Basic 4",
                    'limit': 5,
                    'min_similarity': 0.3,
                    'use_hybrid_search': True,
                    'keyword_weight': 0.3
                }
                
                job = await redis.enqueue_job(
                    'process_retrieval_task',
                    **test_params,
                    _queue_name="retrieval_queue"
                )
                
                print(f"[SUCCESS] ✅ Test job queued:")
                print(f"   - Job ID: {job.job_id}")
                print(f"   - Queue: retrieval_queue")
                print(f"   - Query: {test_params['query']}")
                print(f"   - Subject: {test_params['subject']}")
                print(f"   - Class: {test_params['class_level']}")
                return job.job_id
                
            finally:
                await redis.aclose()
                
        job_id = asyncio.run(enqueue_task())
        return job_id
        
    except Exception as e:
        print(f"[ERROR] ❌ Error enqueuing test task: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
