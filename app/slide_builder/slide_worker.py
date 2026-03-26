"""
ARQ Worker for Slide Generation

Background worker that processes slide generation tasks from the Redis queue.
Run with: python slide_builder/slide_worker.py
"""

import logging
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
    sys.stderr.reconfigure(encoding='utf-8') if hasattr(sys.stderr, 'reconfigure') else None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / 'worker.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from uuid import UUID
from datetime import date

# Redis settings - must match enqueue_slide.py
REDIS_SETTINGS = RedisSettings(host='localhost', port=6379, database=7)
QUEUE_NAME = 'slide_queue'


async def process_slide_task(
    ctx,
    teacher_id: str,
    subject: str,
    class_name: str,
    topic: str = None,
    country: str = "Ghana",
    education_system: str = None,
    education_level: str = None
):
    """
    Process a slide generation task from the queue.
    
    This is called by ARQ when a task is dequeued.
    """
    logger.info(f"🎬 Starting slide generation: {subject}/{class_name}")
    logger.info(f"   Teacher: {teacher_id}")
    logger.info(f"   Topic: {topic or 'Auto-detect'}")
    
    try:
        from app.slide_builder.slide_processor import process_teacher_slides
        
        result = await process_teacher_slides(
            teacher_id=UUID(teacher_id),
            country=country,
            display_name=None
        )
        
        logger.info(f"✅ Slide generation complete: {result} slides processed")
        return {"success": True, "slides_processed": result}
        
    except Exception as e:
        logger.error(f"❌ Slide generation failed: {e}")
        return {"success": False, "error": str(e)}


async def process_session_slide_task(
    ctx,
    teacher_id: str,
    session_id: str,
    subject: str,
    class_name: str,
    indicator_ids: list,
    country: str = "Ghana"
):
    """
    Process slide generation for a specific session.
    
    This is triggered by the timetable scheduler or direct test.
    """
    logger.info(f"🎬 Starting session slide generation")
    logger.info(f"   Session: {session_id}")
    logger.info(f"   Subject: {subject}/{class_name}")
    logger.info(f"   Indicators: {indicator_ids}")
    
    try:
        from app.slide_builder.slide_processor import process_session_slides
        
        # Get today's date
        local_date = date.today()
        
        # Construct session dict as expected by process_session_slides
        session = {
            "id": session_id,
            "subject": subject,
            "class_name": class_name,
            "date": local_date
        }
        
        result = await process_session_slides(
            teacher_id=UUID(teacher_id),
            session=session,
            country=country,
            local_date=local_date
        )
        
        logger.info(f"✅ Session slide generation complete: {result}")
        return {"success": result, "session_id": session_id}
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Session slide generation failed: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def startup(ctx):
    """Worker startup handler"""
    logger.info("🚀 Slide generation worker starting up...")
    logger.info(f"   Queue: {QUEUE_NAME}")
    logger.info(f"   Redis: {REDIS_SETTINGS.host}:{REDIS_SETTINGS.port}/db{REDIS_SETTINGS.database}")


async def shutdown(ctx):
    """Worker shutdown handler"""
    logger.info("📴 Slide generation worker shutting down...")


class WorkerSettings:
    """ARQ worker configuration"""
    functions = [process_slide_task, process_session_slide_task]
    redis_settings = REDIS_SETTINGS
    queue_name = QUEUE_NAME
    max_jobs = 3  # Process 3 slides concurrently
    job_timeout = 900  # 15 minutes per slide (images take time)
    keep_result = 3600  # Keep results for 1 hour
    on_startup = startup
    on_shutdown = shutdown


async def main():
    """Run the worker"""
    logger.info("=" * 70)
    logger.info("Starting Slide Generation Worker")
    logger.info("=" * 70)
    
    worker = Worker(
        functions=WorkerSettings.functions,
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
