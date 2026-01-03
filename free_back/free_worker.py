"""
ARQ Worker for Free Plan Generation

Processes AI-powered semester plan generation tasks.
"""

import logging
import asyncio
import sys
from pathlib import Path
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker, func

# Add parent directory to path so we can import free_back
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging to show in terminal AND file with UTF-8 encoding for emoji support
import codecs
import locale

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
    sys.stderr.reconfigure(encoding='utf-8') if hasattr(sys.stderr, 'reconfigure') else None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Show in terminal
        logging.FileHandler(Path(__file__).parent / 'worker.log', encoding='utf-8')  # Log to file with UTF-8
    ]
)
logger = logging.getLogger(__name__)

# Import the processor
try:
    from free_back.free_processor import process_free_plan_task
    logger.info("✅ Free plan processor imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import free plan processor: {e}")
    raise


# Redis settings (must match enqueue_free.py)
class WorkerSettings:
    """ARQ Worker Settings for Free Plan"""
    redis_settings = RedisSettings(
        host="localhost",
        port=6379,
        database=5,  # Same as enqueue_free.py
        conn_timeout=10,
        conn_retries=5,
        conn_retry_delay=1
    )
    
    functions = [process_free_plan_task]
    queue_name = "free_plan_queue"
    max_tries = 5
    retry_jobs = True
    job_timeout = 600  # 10 minutes
    keep_result = 3600  # Keep results for 1 hour
    max_jobs = 50
    health_check_interval = 60
    allow_abort_jobs = True


async def main():
    """Run the free plan worker"""
    logger.info("=" * 60)
    logger.info("🆓 [FREE PLAN WORKER] Starting...")
    logger.info("=" * 60)
    
    worker = Worker(
        functions = [process_free_plan_task],
        redis_settings=WorkerSettings.redis_settings,
        queue_name=WorkerSettings.queue_name,
        max_tries=WorkerSettings.max_tries,
        job_timeout=WorkerSettings.job_timeout,
        keep_result=WorkerSettings.keep_result,
        max_jobs=WorkerSettings.max_jobs,
        health_check_interval=WorkerSettings.health_check_interval,
        allow_abort_jobs=WorkerSettings.allow_abort_jobs
    )
    
    await worker.async_run()


if __name__ == "__main__":
    logger.info("Starting Free Plan Worker...")
    asyncio.run(main())
