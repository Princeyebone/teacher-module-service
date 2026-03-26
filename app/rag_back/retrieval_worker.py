"""
ARQ Worker for Retrieval Tasks

This module defines the configuration for the ARQ workers that process retrieval queries.
Configured for 3 concurrent workers with proper retry measures.

Usage:
    python -m arq rag_back.retrieval_worker
    
Or use the run script:
    python rag_back/run_retrieval_workers.py
"""

import sys
import os
import logging
import asyncio
from arq.connections import RedisSettings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the retrieval processing function
try:
    from app.rag.retrieval_task import process_retrieval_task
except ImportError as e:
    logger.error(f"Failed to import retrieval task: {e}")
    raise

# Import ARQ worker
try:
    from arq.worker import run_worker
except ImportError:
    from arq import run_worker

# Redis settings for retrieval tasks - using database 3 to avoid conflicts
retrieval_redis_settings = RedisSettings(
    host="localhost", 
    port=6379, 
    database=3,  # Separate DB for retrieval queue
    conn_timeout=10, 
    conn_retries=5, 
    conn_retry_delay=1
)

# Worker configuration with retry measures
worker_config = {
    'functions': [process_retrieval_task],
    'redis_settings': retrieval_redis_settings,
    'queue_name': 'retrieval_queue',
    'max_tries': 5,  # Retry failed jobs up to 5 times
    'retry_delay': 10,  # Wait 10 seconds before retrying
    'job_timeout': 120,  # 2 minutes max per job (retrieval should be fast)
    'concurrent_jobs': 3,  # 3 concurrent jobs per worker
    'keep_result': 1800,  # Keep job results for 30 minutes
    'max_jobs': 100,
    'health_check_interval': 60,  # Health check every 60 seconds
}

# Custom retry handler
async def on_job_error(ctx, job, exc):
    """Handle job errors with custom retry logic"""
    job_id = getattr(job, 'job_id', 'unknown')
    logger.error(f"❌ Job {job_id} failed with error: {exc}")
    
    # Check if we should retry
    try_count = getattr(ctx, 'job_try', 1)
    max_tries = worker_config.get('max_tries', 5)
    
    if try_count < max_tries:
        delay = worker_config.get('retry_delay', 10) * try_count  # Exponential backoff
        logger.info(f"🔄 Will retry job {job_id} in {delay}s (attempt {try_count}/{max_tries})")
    else:
        logger.error(f"❌ Job {job_id} failed after {max_tries} attempts. Giving up.")

# Add error handler to config
worker_config['on_job_failure'] = on_job_error


async def startup(ctx):
    """Startup hook - runs when worker starts"""
    logger.info("🚀 Retrieval worker starting up...")
    logger.info(f"   Queue: {worker_config['queue_name']}")
    logger.info(f"   Concurrent jobs: {worker_config['concurrent_jobs']}")
    logger.info(f"   Max retries: {worker_config['max_tries']}")
    logger.info(f"   Job timeout: {worker_config['job_timeout']}s")


async def shutdown(ctx):
    """Shutdown hook - runs when worker stops"""
    logger.info("👋 Retrieval worker shutting down...")


# Add lifecycle hooks
worker_config['on_startup'] = startup
worker_config['on_shutdown'] = shutdown


def main():
    """Main function to run the retrieval worker"""
    try:
        logger.info("=" * 60)
        logger.info("[STARTING] Retrieval Worker")
        logger.info("=" * 60)
        logger.info("[CONFIG] Worker Configuration:")
        for key, value in worker_config.items():
            if key not in ['functions', 'redis_settings', 'on_job_failure', 'on_startup', 'on_shutdown']:
                logger.info(f"   - {key}: {value}")
        logger.info("=" * 60)
        
        # Run the worker
        run_worker(worker_config)
        
    except KeyboardInterrupt:
        logger.info("\n[STOPPED] Retrieval worker stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
