#!/usr/bin/env python3
"""
ARQ Worker for Academic Calendar File Processing

This script runs the ARQ worker specifically for processing academic calendar files.
It can be run alongside the main schedule generation worker or separately.

Usage:
    python run_calendar_worker.py
    
    # Or use ARQ directly:
    python -m arq calendar_back.calendar_worker_config
"""

import asyncio
import sys
import logging
import os

# Add parent directory to path to import from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Handle imports for both direct execution and module import
try:
    from .calendar_back import calendar_worker_config
except ImportError:
    # If running as script directly, add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ca_ground.calendar_back import calendar_worker_config

from arq import run_worker

# Configure logging with UTF-8 encoding to prevent Unicode errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('calendar_worker.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main function to run the calendar processing worker"""
    try:
        logger.info("[STARTING] Academic Calendar Processing Worker...")
        logger.info("[CONFIG] Worker Configuration:")
        logger.info(f"   - Max Tries: {calendar_worker_config['max_tries']}")
        logger.info(f"   - Job Timeout: {calendar_worker_config['job_timeout']} seconds")
        logger.info(f"   - Concurrent Jobs: {calendar_worker_config['concurrent_jobs']}")
        logger.info(f"   - Retry Delay: {calendar_worker_config['retry_delay']} seconds")
        
        # Run the worker
        run_worker(calendar_worker_config)
        
    except KeyboardInterrupt:
        logger.info("[STOPPED] Worker stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()