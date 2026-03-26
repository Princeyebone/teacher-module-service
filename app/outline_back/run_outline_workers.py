"""
Run multiple outline generation workers
"""

import sys
import subprocess
import time
import signal
from pathlib import Path

# Number of workers to run
NUM_WORKERS = 2

def start_workers():
    """Start multiple worker processes"""
    worker_script = Path(__file__).parent / "outline_worker.py"
    processes = []
    
    print("=" * 70)
    print(f"Starting {NUM_WORKERS} Outline Generation Workers")
    print("=" * 70)
    print(f"Worker script: {worker_script}")
    print("Queue: outline_queue")
    print("Redis: localhost:6379/6")
    print("=" * 70)
    print()
    
    try:
        for i in range(NUM_WORKERS):
            print(f"Starting worker {i+1}/{NUM_WORKERS}...")
            
            process = subprocess.Popen(
                [sys.executable, str(worker_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            processes.append(process)
            
            # Check if worker crashed immediately
            time.sleep(1)
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=1)
                print(f"❌ Worker {i+1} crashed immediately!")
                print(f"   Exit code: {process.returncode}")
                if stdout:
                    print(f"   STDOUT: {stdout}")
                if stderr:
                    print(f"   STDERR: {stderr}")
                continue
            
            print(f"✅ Worker {i+1} started (PID: {process.pid})")
        
        print()
        print("=" * 70)
        print(f"All {len(processes)} workers running")
        print("Press Ctrl+C to stop all workers")
        print("=" * 70)
        print()
        
        # Monitor workers
        while True:
            time.sleep(5)
            
            # Check for dead workers
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    print(f"⚠️  Worker {i+1} (PID {process.pid}) died unexpectedly!")
                    stdout, stderr = process.communicate(timeout=1)
                    if stdout:
                        print(f"   STDOUT: {stdout[-500:]}")  # Last 500 chars
                    if stderr:
                        print(f"   STDERR: {stderr[-500:]}")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping all workers...")
        
        for i, process in enumerate(processes):
            if process.poll() is None:  # Still running
                print(f"   Stopping worker {i+1} (PID {process.pid})...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"   Force killing worker {i+1}...")
                    process.kill()
        
        print("✅ All workers stopped")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        
        # Clean up
        for process in processes:
            if process.poll() is None:
                process.terminate()

if __name__ == "__main__":
    start_workers()
