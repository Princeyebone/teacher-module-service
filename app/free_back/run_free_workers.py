"""
Run Free Plan Workers

Start multiple workers for AI-powered free plan generation.
"""

import subprocess
import sys
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Number of workers
NUM_WORKERS = 2

def start_workers():
    """Start free plan workers"""
    logger.info("=" * 70)
    logger.info("🆓 STARTING FREE PLAN WORKERS")
    logger.info("=" * 70)
    logger.info(f"Number of workers: {NUM_WORKERS}")
    logger.info(f"Queue: free_plan_queue")
    logger.info(f"Redis DB: 5")
    logger.info("=" * 70)
    
    # Get the worker script path
    worker_script = Path(__file__).parent / "free_worker.py"
    
    processes = []
    
    for i in range(NUM_WORKERS):
        logger.info(f"\n🚀 Starting Worker {i+1}/{NUM_WORKERS}...")
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(worker_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            processes.append(process)
            logger.info(f"✅ Worker {i+1} started (PID: {process.pid})")
            
            # Check if it crashes immediately
            time.sleep(2)
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=1)
                logger.error(f"❌ Worker {i+1} crashed immediately!")
                logger.error(f"STDOUT:\n{stdout}")
                logger.error(f"STDERR:\n{stderr}")
                continue
            
        except Exception as e:
            logger.error(f"❌ Failed to start Worker {i+1}: {e}")
    
    if not processes:
        logger.error("❌ No workers started successfully!")
        return
    
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ {len(processes)} Free Plan Workers Running")
    logger.info("=" * 70)
    logger.info("\nPress Ctrl+C to stop all workers\n")
    
    try:
        # Monitor workers
        while True:
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    # Worker crashed, show output
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                        logger.warning(f"⚠️ Worker {i+1} stopped unexpectedly (Exit code: {process.returncode})")
                        if stdout:
                            logger.warning(f"Worker {i+1} STDOUT:\n{stdout[:500]}")
                        if stderr:
                            logger.error(f"Worker {i+1} STDERR:\n{stderr[:500]}")
                    except:
                        logger.warning(f"⚠️ Worker {i+1} stopped unexpectedly")
                    
                    # Remove from processes list to avoid repeated warnings
                    processes[i] = None
            
            # Remove None entries
            processes = [p for p in processes if p is not None]
            
            if not processes:
                logger.error("❌ All workers have crashed!")
                break
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Stopping all workers...")
        for i, process in enumerate(processes):
            if process:
                logger.info(f"Terminating Worker {i+1}...")
                process.terminate()
        
        # Wait for all to finish
        for process in processes:
            if process:
                process.wait()
        
        logger.info("✅ All workers stopped")


if __name__ == "__main__":
    start_workers()
