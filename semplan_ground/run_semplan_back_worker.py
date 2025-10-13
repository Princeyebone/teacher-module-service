#!/usr/bin/env python3
"""
ARQ Worker for Semester Plan File Processing

This script runs the ARQ worker specifically for processing semester plan files.
It can be run alongside other workers or separately.

Usage:
    python run_semplan_back_worker.py
    
    # Or use ARQ directly:
    python -m arq semplan_back.semplan_worker_config
"""

import asyncio
import sys
import logging
from arq import run_worker

# Handle imports for both direct execution and module import
try:
    from .semplan_back import semplan_worker_config
except ImportError:
    # If running as script directly, add parent directory to path
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from semplan_ground.semplan_back import semplan_worker_config

# Configure logging with UTF-8 encoding to prevent Unicode errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('semplan_worker.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main function to run the semester plan processing worker"""
    try:
        logger.info("[STARTING] Semester Plan Processing Worker...")
        logger.info("[CONFIG] Worker Configuration:")
        logger.info(f"   - Max Tries: {semplan_worker_config['max_tries']}")
        logger.info(f"   - Job Timeout: {semplan_worker_config['job_timeout']} seconds")
        logger.info(f"   - Concurrent Jobs: {semplan_worker_config['concurrent_jobs']}")
        logger.info(f"   - Retry Delay: {semplan_worker_config['retry_delay']} seconds")
        logger.info(f"   - Queue Name: semplan_queue")
        
        # Run the worker
        run_worker(semplan_worker_config)
        
    except KeyboardInterrupt:
        logger.info("[STOPPED] Worker stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()