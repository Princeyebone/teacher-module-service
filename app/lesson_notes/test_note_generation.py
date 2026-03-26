"""
Test Weekly Lesson Note Generation

Run this to immediately test lesson note generation regardless of time/day.
Usage: python lesson_notes/test_note_generation.py
"""

import sys
import os
import asyncio
import logging
import traceback
from datetime import datetime, date, timedelta
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.lesson_notes.note_processor import (
    process_teacher_lesson_notes,
    get_all_teachers,
    get_teacher_subject_classes,
    get_indicators_for_coming_week,
    get_current_week_friday,
    get_coming_week_dates,
    get_semester_info,
    get_duration_from_timetable,
    detail_logger
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_data_fetching(teacher_id: UUID, country: str):
    """Test data fetching functions without calling AI."""
    logger.info(f"\n{'='*60}")
    logger.info("📊 TESTING DATA FETCHING")
    logger.info(f"{'='*60}")
    
    # Test dates
    week_friday = get_current_week_friday(country)
    coming_week_start, coming_week_end = get_coming_week_dates(country)
    
    logger.info(f"📅 CURRENT week's Friday (stored as week_date): {week_friday}")
    logger.info(f"📅 COMING week range (indicator search): {coming_week_start} to {coming_week_end}")
    logger.info(f"   ℹ️ Lesson notes are FOR the coming week, but use current Friday as the date")
    
    # Test semester info
    semester_info = await get_semester_info(teacher_id)
    logger.info(f"📚 Semester info: {semester_info}")
    
    # Test subject/class combinations
    subject_classes = await get_teacher_subject_classes(teacher_id)
    logger.info(f"📚 Subject/Class combinations: {len(subject_classes)}")
    for sc in subject_classes:
        logger.info(f"   - {sc['subject']} / {sc['class_name']}")
    
    if not subject_classes:
        logger.warning("❌ No subject/class combinations found!")
        return
    
    # Test indicators for first subject/class
    sc = subject_classes[0]
    subject = sc["subject"]
    class_name = sc["class_name"]
    
    logger.info(f"\n📖 Testing indicators for: {subject} - {class_name}")
    
    indicators = await get_indicators_for_coming_week(
        teacher_id, subject, class_name, coming_week_start, coming_week_end
    )
    logger.info(f"📊 Found {len(indicators)} indicators for coming week")
    
    for idx, ind in enumerate(indicators, 1):
        logger.info(f"   {idx}. {ind.get('indicator_code', 'No code')}: {ind.get('indicator_text', '')[:50]}...")
        logger.info(f"      Strand: {ind.get('strand_name')}")
        logger.info(f"      Substrand: {ind.get('substrand_name')}")
    
    # Test duration
    duration = await get_duration_from_timetable(teacher_id, subject, class_name)
    logger.info(f"⏱️ Duration from timetable: {duration or 'Not found'}")


async def test_single_teacher(teacher_id: str, teacher_name: str = None, country: str = "Ghana"):
    """Test lesson note generation for a single teacher."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"👨‍🏫 Testing teacher: {teacher_name or teacher_id}")
    logger.info(f"{'='*60}")
    
    teacher_uuid = UUID(teacher_id)
    
    # First test data fetching
    await test_data_fetching(teacher_uuid, country)
    
    # Then run full generation
    logger.info(f"\n🚀 Running full generation...")
    await process_teacher_lesson_notes(teacher_uuid, country, teacher_name)
    
    logger.info(f"\n✅ Test completed for {teacher_name or teacher_id}")


async def run_test():
    """Main test function."""
    logger.info("\n" + "=" * 70)
    logger.info("  WEEKLY LESSON NOTE GENERATION TEST")
    logger.info("  Running immediately regardless of timezone")
    logger.info("=" * 70)
    
    # Get all teachers
    teachers = await get_all_teachers()
    
    if not teachers:
        logger.error("❌ No teachers found in database!")
        return
    
    logger.info(f"\n📋 Found {len(teachers)} teachers")
    
    for i, teacher in enumerate(teachers):
        logger.info(f"  {i+1}. {teacher.get('display_name', 'Unknown')} ({teacher['id']}) - {teacher.get('country', 'No country')}")
    
    # Process first teacher with data
    for teacher in teachers:
        teacher_id = str(teacher["id"])
        teacher_name = teacher.get("display_name", "Unknown Teacher")
        country = teacher.get("country", "Ghana")
        
        if country:
            await test_single_teacher(teacher_id, teacher_name, country)
            break  # Only test one teacher
    
    logger.info("\n" + "=" * 70)
    logger.info("  TEST COMPLETED")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_test())
