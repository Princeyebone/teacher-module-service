"""
Run multiple slide generation workers

Usage: python slide_builder/run_slide_workers.py
"""

import sys
import subprocess
import time
from pathlib import Path

# Number of workers to run
NUM_WORKERS = 2

def start_workers():
    """Start multiple worker processes"""
    worker_script = Path(__file__).parent / "slide_worker.py"
    processes = []
    
    print("=" * 70)
    print(f"Starting {NUM_WORKERS} Slide Generation Workers")
    print("=" * 70)
    print(f"Worker script: {worker_script}")
    print("Queue: slide_queue")
    print("Redis: localhost:6379/7")
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
                bufsize=1,
                encoding='utf-8'
            )
            
            processes.append(process)
            
            # Check if worker crashed immediately
            time.sleep(1)
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=1)
                print(f"❌ Worker {i+1} crashed immediately!")
                print(f"   Exit code: {process.returncode}")
                if stdout:
                    print(f"   STDOUT: {stdout[:500]}")
                if stderr:
                    print(f"   STDERR: {stderr[:500]}")
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
            time.sleep(10)
            
            # Check for dead workers
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    print(f"⚠️  Worker {i+1} (PID {process.pid}) died unexpectedly!")
                    # Restart it
                    print(f"🔄 Restarting worker {i+1}...")
                    new_process = subprocess.Popen(
                        [sys.executable, str(worker_script)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        encoding='utf-8'
                    )
                    processes[i] = new_process
                    time.sleep(1)
                    if new_process.poll() is None:
                        print(f"✅ Worker {i+1} restarted (PID: {new_process.pid})")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping all workers...")
        
        for i, process in enumerate(processes):
            if process.poll() is None:
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
        
        for process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    start_workers()
