"""
Lesson Brief Scheduler

APScheduler-based scheduler that runs every hour to trigger lesson brief generation.
"""

import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .brief_processor import run_brief_generation_cycle

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


async def scheduled_brief_generation():
    """
    Wrapper function called by the scheduler.
    """
    logger.info(f"⏰ Scheduler triggered at {datetime.utcnow().isoformat()}")
    try:
        await run_brief_generation_cycle()
    except Exception as e:
        logger.error(f"❌ Scheduled job failed: {e}")


def setup_scheduler(scheduler: AsyncIOScheduler):
    """
    Add jobs to the scheduler.
    
    The main job runs every hour at minute 0 to check all teachers
    and generate briefs for those in their 12-2 AM window.
    """
    
    # Run every hour at minute 0
    scheduler.add_job(
        scheduled_brief_generation,
        trigger=CronTrigger(minute=0),  # Every hour at :00
        id='lesson_brief_hourly',
        name='Lesson Brief Generation - Hourly Check',
        replace_existing=True
    )
    
    logger.info("📅 Scheduled job added: Lesson Brief Generation (hourly)")
    
    # Also run immediately on startup (optional - comment out if not needed)
    # scheduler.add_job(
    #     scheduled_brief_generation,
    #     trigger='date',  # Run once immediately
    #     id='lesson_brief_startup',
    #     name='Lesson Brief Generation - Startup',
    #     replace_existing=True
    # )


async def start_scheduler():
    """
    Start the scheduler and keep it running.
    """
    scheduler = create_scheduler()
    setup_scheduler(scheduler)
    
    logger.info("🚀 Starting Lesson Brief Scheduler...")
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
