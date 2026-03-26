"""
ARQ Worker for Embedding Generation Tasks

This module defines the configuration for the ARQ worker that processes embedding generation tasks.

Usage:
    python -m arq rag_back.embedding_worker
    
Or use the run script:
    python rag_back/run_embedding_workers.py
"""

import sys
import logging
from arq.connections import RedisSettings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the embedding processing function
try:
    from app.rag_back.embedding_processing import process_embedding_task
except ImportError:
    # If running as script directly, add parent directory to path
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.rag_back.embedding_processing import process_embedding_task

# Import ARQ worker
try:
    from arq.worker import run_worker
except ImportError:
    from arq import run_worker

# Create Redis settings for embedding tasks
embedding_redis_settings = RedisSettings(
    host="localhost", 
    port=6379, 
    database=0, 
    conn_timeout=10, 
    conn_retries=5, 
    conn_retry_delay=1
)

# Worker configuration
worker_config = {
    'functions': [process_embedding_task],
    'redis_settings': embedding_redis_settings,
    'queue_name': 'embedding_queue',
    'max_tries': 3,
    'retry_delay': 30,
    'job_timeout': 600,  # 10 minutes max per job
    'concurrent_jobs': 1,
    'keep_result': 3600,  # Keep job results for 1 hour
    'max_jobs': 50
}

def main():
    """Main function to run the embedding worker"""
    try:
        logger.info("[STARTING] Embedding Worker...")
        logger.info("[CONFIG] Worker Configuration:")
        for key, value in worker_config.items():
            if key != 'functions' and key != 'redis_settings':
                logger.info(f"   - {key}: {value}")
        
        # Run the worker
        logger.info("Starting ARQ worker...")
        run_worker(worker_config)
    except Exception as e:
        logger.error(f"[ERROR] Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()