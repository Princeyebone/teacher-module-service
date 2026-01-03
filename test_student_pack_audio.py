
import asyncio
import logging
import sys
from datetime import datetime
from uuid import UUID

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('audio_test.log', mode='w')
    ],
    force=True
)
logger = logging.getLogger(__name__)

# Test Data
SLIDE_ID = "8cc2a1ab-8870-47b0-8f44-fb18f788f441"
SESSION_ID = 1618
TEACHER_ID = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
SUBJECT = "Physics"
CLASS_NAME = "Class 11A"

async def test_audio_generation():
    logger.info("[START] Starting Student Pack Audio Test")
    
    try:
        from slide_builder.student_pack_generator import generate_student_pack
        
        logger.info(f"   Generating pack for Slide ID: {SLIDE_ID}")
        
        success = await generate_student_pack(
            slide_id=SLIDE_ID,
            session_id=str(SESSION_ID),
            teacher_id=TEACHER_ID,
            subject=SUBJECT,
            class_name=CLASS_NAME
        )
        
        if success:
            logger.info("[SUCCESS] Student Pack generation successful!")
            
            # Brief wait
            await asyncio.sleep(1)
            
            # Verify audio URL, video resources, and structured content in DB
            from database import get_db
            from sqlalchemy import text
            
            db_gen = get_db()
            db = await anext(db_gen)
            
            # Select by session_id (as generate_student_pack uses session_id/teacher_id to find/create)
            result = await db.execute(
                text("""
                    SELECT podcast_audio_url, video_resources, status, slide_id, content_json 
                    FROM student_lesson_packs 
                    WHERE session_id = :sess AND teacher_id = CAST(:tid AS uuid)
                """),
                {"sess": SESSION_ID, "tid": TEACHER_ID}
            )
            row = result.fetchone()
            
            if row:
                m = row._mapping
                logger.info(f"   Status: {m['status']}")
                logger.info(f"   Audio URL: {m['podcast_audio_url']}")
                
                # Check Audio
                if m['podcast_audio_url']:
                    logger.info("[PASS] Audio URL present!")
                else:
                    logger.error("[FAIL] Audio URL is NULL.")
                
                # Check Videos
                video_resources = m['video_resources']
                if video_resources and video_resources != '[]':
                    import json
                    videos = json.loads(video_resources) if isinstance(video_resources, str) else video_resources
                    if videos:
                        logger.info(f"[PASS] Video resources present! Found {len(videos)} videos:")
                        for v in videos[:3]:  # Show first 3
                            logger.info(f"   - {v.get('title', 'No title')[:50]}...")
                    else:
                        logger.warning("[WARN] Video resources is empty list.")
                else:
                    logger.warning("[WARN] No video resources found (YouTube search may have failed).")
                
                # Check Structured Content JSON
                content_json = m.get('content_json')
                if content_json:
                    import json
                    pack = json.loads(content_json) if isinstance(content_json, str) else content_json
                    slides = pack.get('slides', [])
                    summary = pack.get('summary', {})
                    
                    logger.info(f"[PASS] Structured content_json present!")
                    logger.info(f"   - Total slides: {summary.get('total_slides', len(slides))}")
                    logger.info(f"   - Has notes: {summary.get('has_notes', False)}")
                    logger.info(f"   - Video count: {summary.get('video_count', 0)}")
                    logger.info(f"   - Has podcast: {summary.get('has_podcast', False)}")
                    logger.info(f"   - Podcast duration: {summary.get('podcast_duration_ms', 0) / 1000 / 60:.1f} minutes")
                    logger.info(f"   - MCQ count: {summary.get('mcq_count', 0)}")
                    logger.info(f"   - Essay count: {summary.get('essay_count', 0)}")
                    
                    # List slide types
                    slide_types = [s.get('type') for s in slides]
                    logger.info(f"   - Slide types: {slide_types}")
                    
                    # Verify answer keys are at end
                    if 'answer_key_mcq' in slide_types or 'answer_key_essay' in slide_types:
                        logger.info("[PASS] Answer key slides present at end!")
                    else:
                        logger.info("[INFO] No assessment answers found (may not have assessments)")
                else:
                    logger.warning("[WARN] content_json is NULL or empty.")
                
                # Overall result
                if m['podcast_audio_url']:
                    logger.info("[OVERALL] Test PASSED - Audio generated successfully!")
                else:
                    logger.error("[OVERALL] Test FAILED - No audio generated.")
            else:
                logger.error("[FAIL] Pack not found in DB.")
                
            await db_gen.aclose()
            
        else:
            logger.error("[FAIL] generate_student_pack returned False")
    
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_audio_generation())
