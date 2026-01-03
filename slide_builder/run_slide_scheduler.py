"""
Slide Scheduler Runner

Entry point to start the slide generation scheduler.
Run with: python slide_builder/run_slide_scheduler.py
"""

import asyncio
import sys
import os

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slide_builder.slide_scheduler import start_scheduler


if __name__ == "__main__":
    print("🎬 Starting Slide Generation Scheduler...")
    print("   Slides will be generated at 12 AM (midnight) in each teacher's timezone")
    print("   Press Ctrl+C to stop")
    print()
    
    asyncio.run(start_scheduler())
