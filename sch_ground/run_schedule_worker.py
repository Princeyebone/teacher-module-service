#!/usr/bin/env python3
"""
Schedule Worker Runner for TMDL5

This script provides a convenient way to run the schedule generation worker
from the root directory of the project.

Usage:
    python run_schedule_worker.py [command]
    
Commands:
    start    - Start the schedule worker (default)
    test     - Test Redis connection
    info     - Show worker configuration
    enqueue  - Enqueue a test task
    
Examples:
    python run_schedule_worker.py
    python run_schedule_worker.py start
    python run_schedule_worker.py info
    python run_schedule_worker.py test
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Main function to run the schedule worker"""
    # Get the command from arguments (default to 'start')
    command = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    # Get the path to the arq_worker.py in the same sch_ground directory
    current_dir = Path(__file__).parent
    worker_script = current_dir / "arq_worker.py"
    
    if not worker_script.exists():
        print("[ERROR] Schedule worker script not found!")
        print(f"Expected location: {worker_script}")
        sys.exit(1)
    
    print(f"[STARTING] Running schedule worker with command: {command}")
    print(f"[LOCATION] Worker script: {worker_script}")
    
    try:
        # Run the worker script with the command
        result = subprocess.run([
            sys.executable, str(worker_script), command
        ], check=False)
        
        sys.exit(result.returncode)
        
    except KeyboardInterrupt:
        print("\n[STOPPED] Schedule worker stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Error running schedule worker: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()