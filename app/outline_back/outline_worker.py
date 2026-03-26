"""
ARQ Worker for Course/Subject Outline Generation
"""

import logging
import asyncio
import sys
from pathlib import Path
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker, func

# Add parent directory to path
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
from app.outline_back.outline_processor import process_outline_task

async def startup(ctx):
    """Worker startup handler"""
    logger.info("🚀 Outline worker starting up...")

async def shutdown(ctx):
    """Worker shutdown handler"""
    logger.info("📴 Outline worker shutting down...")

class WorkerSettings:
    """ARQ worker configuration"""
    functions = [process_outline_task]
    redis_settings = RedisSettings(host='localhost', port=6379, database=6)
    queue_name = 'outline_queue'
    max_jobs = 5
    job_timeout = 600  # 10 minutes
    keep_result = 3600  # Keep results for 1 hour
    on_startup = startup
    on_shutdown = shutdown

async def main():
    """Run the worker"""
    logger.info("=" * 70)
    logger.info("Starting Outline Generation Worker")
    logger.info("=" * 70)
    logger.info(f"Queue: {WorkerSettings.queue_name}")
    logger.info(f"Redis: {WorkerSettings.redis_settings.host}:{WorkerSettings.redis_settings.port}")
    logger.info(f"Database: {WorkerSettings.redis_settings.database}")
    logger.info("=" * 70)
    
    worker = Worker(
        functions=[process_outline_task],
        redis_settings=WorkerSettings.redis_settings,
        queue_name=WorkerSettings.queue_name,
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
        keep_result=WorkerSettings.keep_result,
        on_startup=startup,
        on_shutdown=shutdown
    )
    
    await worker.async_run()

if __name__ == "__main__":
    asyncio.run(main())
