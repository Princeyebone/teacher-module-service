"""
ARQ Worker for Curriculum Processing Tasks

This module defines the configuration for the ARQ workers that process curriculum files
through the combined RAG pipeline (extraction, embedding, retrieval, AI processing).

Configured for 2 workers with proper retry measures.

Usage:
    python -m arq curri_back.curri_worker
    
Or use the run script:
    python curri_back/run_curri_workers.py
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

# Import the curriculum processing function
try:
    from app.curri_back.curri_processor import process_curriculum_task
    logger.info("✅ Curriculum processor imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import curriculum processor: {e}")
    raise

# Import ARQ worker
try:
    from arq.worker import run_worker
except ImportError:
    from arq import run_worker

# Redis settings for curriculum tasks - using database 4 to avoid conflicts
curri_redis_settings = RedisSettings(
    host="localhost", 
    port=6379, 
    database=4,  # Separate DB for curriculum queue
    conn_timeout=10, 
    conn_retries=5, 
    conn_retry_delay=1
)

# Worker configuration with retry measures
worker_config = {
    'functions': [process_curriculum_task],
    'redis_settings': curri_redis_settings,
    'queue_name': 'curriculum_queue',
    'max_tries': 5,  # Retry failed jobs up to 5 times
    'retry_delay': 30,  # Wait 30 seconds before retrying (longer for heavy processing)
    'job_timeout': 600,  # 10 minutes max per job (includes extraction + embedding + AI)
    'concurrent_jobs': 1,  # 1 concurrent job per worker (heavy processing)
    'keep_result': 3600,  # Keep job results for 1 hour
    'max_jobs': 50,
    'health_check_interval': 60,  # Health check every 60 seconds
}


async def on_job_error(ctx, job, exc):
    """Handle job errors with custom retry logic"""
    job_id = getattr(job, 'job_id', 'unknown')
    logger.error(f"❌ Curriculum job {job_id} failed with error: {exc}")
    
    try_count = getattr(ctx, 'job_try', 1)
    max_tries = worker_config.get('max_tries', 5)
    
    if try_count < max_tries:
        delay = worker_config.get('retry_delay', 30) * try_count  # Exponential backoff
        logger.info(f"🔄 Will retry curriculum job {job_id} in {delay}s (attempt {try_count}/{max_tries})")
    else:
        logger.error(f"❌ Curriculum job {job_id} failed after {max_tries} attempts. Giving up.")


# Add error handler to config
worker_config['on_job_failure'] = on_job_error


async def startup(ctx):
    """Startup hook - runs when worker starts"""
    logger.info("=" * 60)
    logger.info("🚀 Curriculum Processing Worker Starting Up...")
    logger.info("=" * 60)
    logger.info(f"   Queue: {worker_config['queue_name']}")
    logger.info(f"   Concurrent jobs: {worker_config['concurrent_jobs']}")
    logger.info(f"   Max retries: {worker_config['max_tries']}")
    logger.info(f"   Job timeout: {worker_config['job_timeout']}s")
    logger.info("=" * 60)


async def shutdown(ctx):
    """Shutdown hook - runs when worker stops"""
    logger.info("👋 Curriculum Processing Worker Shutting Down...")


# Add lifecycle hooks
worker_config['on_startup'] = startup
worker_config['on_shutdown'] = shutdown


def main():
    """Main function to run the curriculum worker"""
    try:
        logger.info("=" * 60)
        logger.info("[STARTING] Curriculum Processing Worker")
        logger.info("=" * 60)
        logger.info("[CONFIG] Worker Configuration:")
        for key, value in worker_config.items():
            if key not in ['functions', 'redis_settings', 'on_job_failure', 'on_startup', 'on_shutdown']:
                logger.info(f"   - {key}: {value}")
        logger.info("=" * 60)
        
        # Run the worker
        run_worker(worker_config)
        
    except KeyboardInterrupt:
        logger.info("\n[STOPPED] Curriculum worker stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
