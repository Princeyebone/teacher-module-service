"""
Weekly Lesson Note Scheduler

APScheduler-based scheduler that runs every hour to trigger lesson note generation.
Checks if teachers are in the Wednesday/Thursday 12-2 AM window before processing.
"""

import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .note_processor import run_lesson_note_generation_cycle

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


async def scheduled_lesson_note_generation():
    """
    Wrapper function called by the scheduler.
    """
    logger.info(f"⏰ Lesson Note Scheduler triggered at {datetime.utcnow().isoformat()}")
    try:
        await run_lesson_note_generation_cycle()
    except Exception as e:
        logger.error(f"❌ Scheduled job failed: {e}")


def setup_scheduler(scheduler: AsyncIOScheduler):
    """
    Add jobs to the scheduler.
    
    The main job runs every hour at minute 0 to check all teachers
    and generate lesson notes for those in their Wednesday/Thursday 12-2 AM window.
    """
    
    # Run every hour at minute 0
    scheduler.add_job(
        scheduled_lesson_note_generation,
        trigger=CronTrigger(minute=0),  # Every hour at :00
        id='lesson_note_hourly',
        name='Weekly Lesson Note Generation - Hourly Check',
        replace_existing=True
    )
    
    logger.info("📅 Scheduled job added: Weekly Lesson Note Generation (hourly)")
    logger.info("   Window: Wednesday 12-2 AM OR Thursday 12-2 AM (teacher's local time)")


async def start_scheduler():
    """
    Start the scheduler and keep it running.
    """
    scheduler = create_scheduler()
    setup_scheduler(scheduler)
    
    logger.info("🚀 Starting Weekly Lesson Note Scheduler...")
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
