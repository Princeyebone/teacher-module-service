"""
Run Student Support Pack Workers

Starts multiple worker processes that poll the database for pending
student support packs and process them.

Usage: python student_back/run_workers.py
"""

import sys
import subprocess
import time
from pathlib import Path

# Number of workers to run
NUM_WORKERS = 2

def start_workers():
    """Start multiple worker processes"""
    worker_script = Path(__file__).parent / "worker.py"
    processes = []
    
    print("=" * 70)
    print(f"Starting {NUM_WORKERS} Student Support Pack Workers")
    print("=" * 70)
    print(f"Worker script: {worker_script}")
    print("Processing: student_support_packs table (status='pending')")
    print("=" * 70)
    print()
    
    try:
        for i in range(NUM_WORKERS):
            print(f"Starting worker {i+1}/{NUM_WORKERS}...")
            
            process = subprocess.Popen(
                [sys.executable, str(worker_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8'
            )
            
            processes.append(process)
            
            # Check if worker crashed immediately
            time.sleep(2)
            if process.poll() is not None:
                stdout, _ = process.communicate(timeout=1)
                print(f"❌ Worker {i+1} crashed immediately!")
                print(f"   Exit code: {process.returncode}")
                if stdout:
                    print(f"   Output: {stdout[:500]}")
                continue
            
            print(f"✅ Worker {i+1} started (PID: {process.pid})")
        
        print()
        print("=" * 70)
        print(f"All {len(processes)} workers running")
        print("Press Ctrl+C to stop all workers")
        print("=" * 70)
        print()
        
        # Monitor workers and print their output
        while True:
            for i, process in enumerate(processes):
                # Check for output
                if process.stdout:
                    try:
                        line = process.stdout.readline()
                        if line:
                            print(f"[Worker {i+1}] {line.strip()}")
                    except:
                        pass
                
                # Check for dead workers and restart them
                if process.poll() is not None:
                    print(f"⚠️  Worker {i+1} (PID {process.pid}) died unexpectedly!")
                    print(f"🔄 Restarting worker {i+1}...")
                    
                    new_process = subprocess.Popen(
                        [sys.executable, str(worker_script)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        encoding='utf-8'
                    )
                    processes[i] = new_process
                    time.sleep(1)
                    
                    if new_process.poll() is None:
                        print(f"✅ Worker {i+1} restarted (PID: {new_process.pid})")
            
            time.sleep(0.1)  # Small sleep to prevent CPU spin
        
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
