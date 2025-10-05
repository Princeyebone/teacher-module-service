#!/usr/bin/env python3
"""
ARQ Worker for Timetable File Processing

This script runs the ARQ worker specifically for processing timetable files.
It can be run alongside the main schedule generation worker or separately.

Usage:
    python run_timetable_worker.py
    
    # Or use ARQ directly:
    python -m arq table_back.timetable_worker_config
"""

import asyncio
import sys
import logging
from arq import run_worker

# Handle imports for both direct execution and module import
try:
    from .table_back import timetable_worker_config
except ImportError:
    # If running as script directly, add parent directory to path
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from t_ground.table_back import timetable_worker_config

# Configure logging with UTF-8 encoding to prevent Unicode errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('timetable_worker.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main function to run the timetable processing worker"""
    try:
        logger.info("[STARTING] Timetable Processing Worker...")
        logger.info("[CONFIG] Worker Configuration:")
        logger.info(f"   - Max Tries: {timetable_worker_config['max_tries']}")
        logger.info(f"   - Job Timeout: {timetable_worker_config['job_timeout']} seconds")
        logger.info(f"   - Concurrent Jobs: {timetable_worker_config['concurrent_jobs']}")
        logger.info(f"   - Retry Delay: {timetable_worker_config['retry_delay']} seconds")
        
        # Run the worker
        run_worker(timetable_worker_config)
        
    except KeyboardInterrupt:
        logger.info("[STOPPED] Worker stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()