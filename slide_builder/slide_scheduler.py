"""
Slide Scheduler

APScheduler-based scheduler that runs every hour to trigger slide generation.
Generates slides at midnight (12 AM) in each teacher's local timezone.

NOTE: This now ENQUEUES tasks to Redis queue instead of direct processing.
      Run slide_builder/run_slide_workers.py to process the queue.
"""

import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .slide_processor import enqueue_slide_generation_cycle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.
    
    Returns:
        Configured AsyncIOScheduler
    """
    scheduler = AsyncIOScheduler(
        job_defaults={
            'coalesce': True,  # Combine multiple missed runs into one
            'max_instances': 1,  # Only one instance of each job at a time
            'misfire_grace_time': 60  # Allow 60 seconds grace for missed jobs
        }
    )
    
    return scheduler


async def scheduled_slide_generation():
    """
    Wrapper function called by the scheduler.
    Enqueues slide generation tasks to Redis queue (non-blocking).
    """
    logger.info(f"⏰ Slide Scheduler triggered at {datetime.utcnow().isoformat()}")
    try:
        count = await enqueue_slide_generation_cycle()
        logger.info(f"✅ Enqueued {count} slide generation tasks")
    except Exception as e:
        logger.error(f"❌ Scheduled slide enqueue failed: {e}")


def setup_scheduler(scheduler: AsyncIOScheduler):
    """
    Add jobs to the scheduler.
    
    The main job runs every hour at minute 0 to check all teachers
    and generate slides for those at midnight in their timezone.
    """
    
    # Run every hour at minute 0
    scheduler.add_job(
        scheduled_slide_generation,
        trigger=CronTrigger(minute=0),  # Every hour at :00
        id='slide_generation_hourly',
        name='Slide Generation - Hourly Check (targets 12 AM local time)',
        replace_existing=True
    )
    
    logger.info("📅 Scheduled job added: Slide Generation (hourly)")
    logger.info("   Target: 12 AM (midnight) in each teacher's local timezone")


async def start_scheduler():
    """
    Start the scheduler and keep it running.
    """
    scheduler = create_scheduler()
    setup_scheduler(scheduler)
    
    logger.info("🚀 Starting Slide Generation Scheduler...")
    scheduler.start()
    
    # Print scheduled jobs
    jobs = scheduler.get_jobs()
    logger.info(f"📋 Scheduled jobs ({len(jobs)}):")
    for job in jobs:
        logger.info(f"   - {job.name}: {job.trigger}")
    
    # Keep the scheduler running
    try:
        while True:
            await asyncio.sleep(60)  # Sleep for 60 seconds
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Shutting down scheduler...")
        scheduler.shutdown()
        logger.info("✅ Scheduler stopped")


# For direct execution
if __name__ == "__main__":
    asyncio.run(start_scheduler())
