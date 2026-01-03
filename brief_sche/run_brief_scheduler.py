"""
Run Lesson Brief Scheduler

Entry point to start the lesson brief scheduler.
Usage: python -m brief_sche.run_brief_scheduler
   or: python brief_sche/run_brief_scheduler.py
"""

import sys
import os
import asyncio
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brief_sche.brief_scheduler import start_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("  LESSON BRIEF SCHEDULER")
    logger.info("=" * 60)
    logger.info("")
    logger.info("This scheduler runs every hour and checks for teachers")
    logger.info("whose local time is between 12:00 AM and 2:00 AM.")
    logger.info("For those teachers, it generates lesson briefs for all")
    logger.info("their classes scheduled for that day.")
    logger.info("")
    logger.info("Press Ctrl+C to stop the scheduler.")
    logger.info("")
    logger.info("=" * 60)
    
    try:
        asyncio.run(start_scheduler())
    except KeyboardInterrupt:
        logger.info("\n🛑 Scheduler stopped by user")
    except Exception as e:
        logger.error(f"❌ Scheduler failed: {e}")
        raise


if __name__ == "__main__":
    main()
