"""
ARQ Worker for Student Support Pack Generation

Background worker that processes pack generation tasks from the Redis queue.
Run with: python student_back/support_pack_worker.py
"""

import logging
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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
from typing import List, Optional

# Redis settings - must match enqueue_support_pack.py
REDIS_SETTINGS = RedisSettings(host='localhost', port=6379, database=8)
QUEUE_NAME = 'student_support_queue'


async def process_student_support_pack(
    ctx,
    pack_id: str,
    teacher_id: str,
    student_name: str,
    subject: str,
    class_name: str,
    topic: str,
    interests: List[str],
    health_considerations: Optional[str],
    edu_sys: Optional[str],
    edu_lvl: Optional[str]
):
    """
    Process a student support pack generation task from the queue.
    
    This is called by ARQ when a task is dequeued.
    """
    logger.info(f"🎬 Starting pack generation for {student_name}")
    logger.info(f"   Pack ID: {pack_id}")
    logger.info(f"   Topic: {topic}")
    logger.info(f"   Interests: {interests}")
    
    try:
        from student_back.student_support_generator import generate_student_support_pack
        
        result = await generate_student_support_pack(
            pack_id=pack_id,
            teacher_id=teacher_id,
            student_name=student_name,
            subject=subject,
            class_name=class_name,
            topic=topic,
            interests=interests,
            health_considerations=health_considerations,
            edu_sys=edu_sys,
            edu_lvl=edu_lvl
        )
        
        logger.info(f"✅ Pack generation complete for {student_name}")
        return {"success": result, "pack_id": pack_id}
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Pack generation failed: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


async def startup(ctx):
    """Worker startup handler"""
    logger.info("🚀 Student Support Pack worker starting up...")
    logger.info(f"   Queue: {QUEUE_NAME}")
    logger.info(f"   Redis: {REDIS_SETTINGS.host}:{REDIS_SETTINGS.port}/db{REDIS_SETTINGS.database}")


async def shutdown(ctx):
    """Worker shutdown handler"""
    logger.info("📴 Student Support Pack worker shutting down...")


class WorkerSettings:
    """ARQ worker configuration"""
    functions = [process_student_support_pack]
    redis_settings = REDIS_SETTINGS
    queue_name = QUEUE_NAME
    max_jobs = 2  # Process 2 packs concurrently
    job_timeout = 1200  # 20 minutes per pack (AI + images take time)
    keep_result = 3600  # Keep results for 1 hour
    on_startup = startup
    on_shutdown = shutdown


async def main():
    """Run the worker"""
    logger.info("=" * 70)
    logger.info("Starting Student Support Pack Worker")
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
