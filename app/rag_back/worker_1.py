#!/usr/bin/env python3
"""
ARQ Worker 1 for Text Extraction and Chunking Tasks

This script runs the first ARQ worker specifically for processing text extraction 
and chunking tasks using the implementation from rag/text.py.

Usage:
    python worker_1.py
    
    # Or use ARQ directly:
    python -m arq rag_back.worker_1
"""

import asyncio
import sys
import logging
from arq import run_worker

# Handle imports for both direct execution and module import
try:
    from .rag_back import worker_config_1
except ImportError:
    # If running as script directly, add parent directory to path
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.rag_back.rag_back import worker_config_1

# Configure logging with UTF-8 encoding to prevent Unicode errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('worker_1.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main function to run the text chunking worker 1"""
    try:
        logger.info("[STARTING] Text Chunking Worker 1...")
        logger.info("[CONFIG] Worker Configuration:")
        logger.info(f"   - Max Tries: {worker_config_1['max_tries']}")
        logger.info(f"   - Job Timeout: {worker_config_1['job_timeout']} seconds")
        logger.info(f"   - Concurrent Jobs: {worker_config_1['concurrent_jobs']}")
        logger.info(f"   - Retry Delay: {worker_config_1['retry_delay']} seconds")
        logger.info(f"   - Queue Name: {worker_config_1['queue_name']}")
        
        # Run the worker
        run_worker(worker_config_1)
        
    except KeyboardInterrupt:
        logger.info("[STOPPED] Worker stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()