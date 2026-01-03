"""
============================================================================
COMPREHENSIVE SLIDE GENERATION TEST
============================================================================
Tests the complete slide generation flow:
1. Database connection
2. Session finding
3. Curriculum retrieval
4. RAG retrieval
5. AI generation
6. Slide saving
7. Image prompt saving
8. Image generation

Run: python slide_builder/test_complete_flow.py
============================================================================
"""

import asyncio
import sys
import os
import logging
import json
import traceback
from pathlib import Path
from datetime import datetime, date
from uuid import UUID

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup detailed logging to both console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('slide_builder/test_flow.log', encoding='utf-8', mode='w')
    ]
)
logger = logging.getLogger("test_flow")

# Test teacher ID
TEST_TEACHER_ID = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
TEST_COUNTRY = "Ghana"


def print_section(title: str):
    """Print a section header."""
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"  {title}")
    logger.info("=" * 70)


def print_result(success: bool, message: str):
    """Print a test result."""
    icon = "✅" if success else "❌"
    logger.info(f"{icon} {message}")


async def test_database_connection():
    """Test 1: Verify database connection."""
    print_section("TEST 1: Database Connection")
    
    try:
        from database import get_db
        from sqlalchemy import text
        
        db_gen = get_db()
        db = await anext(db_gen)
        
        result = await db.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        
        await db_gen.aclose()
        
        if row and row._mapping["test"] == 1:
            print_result(True, "Database connection works")
            return True
        else:
            print_result(False, "Unexpected query result")
            return False
            
    except Exception as e:
        print_result(False, f"Database connection failed: {e}")
        logger.error(traceback.format_exc())
        return False


async def test_find_session():
    """Test 2: Find a session with curriculum data."""
    print_section("TEST 2: Find Session with Curriculum")
    
    try:
        from database import get_db
        from sqlalchemy import text
        
        db_gen = get_db()
        db = await anext(db_gen)
        
        # First, find sessions for this teacher
        result = await db.execute(
            text("""
                SELECT id, subject, class_name, date, start_time, end_time
                FROM classsession
                WHERE teacher_id = CAST(:tid AS uuid)
                  AND is_completed = false
                ORDER BY date
                LIMIT 10
            """),
            {"tid": TEST_TEACHER_ID}
        )
        sessions = result.fetchall()
        
        if not sessions:
            print_result(False, "No sessions found for teacher")
            await db_gen.aclose()
            return None
        
        logger.info(f"   Found {len(sessions)} total sessions")
        
        # Check which sessions have curriculum data
        for session in sessions:
            s = session._mapping
            session_id = s["id"]
            
            # Check if this session has curriculum
            curr_result = await db.execute(
                text("""
                    SELECT i.id, i.indicator_text, s.strand_name
                    FROM indicator i
                    LEFT JOIN contentstandard cs ON i.content_standard_id = cs.id
                    LEFT JOIN substrand ss ON cs.substrand_id = ss.id
                    LEFT JOIN strand s ON ss.strand_id = s.id
                    WHERE i.teacher_id = CAST(:tid AS uuid)
                      AND i.subject = :subject
                      AND i.class_name = :class_name
                      AND i.session_details IS NOT NULL
                      AND i.session_details @> :session_json
                    LIMIT 1
                """),
                {
                    "tid": TEST_TEACHER_ID,
                    "subject": s["subject"],
                    "class_name": s["class_name"],
                    "session_json": json.dumps([{"id": session_id}])
                }
            )
            curr_row = curr_result.fetchone()
            
            if curr_row:
                await db_gen.aclose()
                session_data = {
                    "id": session_id,
                    "subject": s["subject"],
                    "class_name": s["class_name"],
                    "date": s["date"]
                }
                print_result(True, f"Found session with curriculum:")
                logger.info(f"      Session ID: {session_id}")
                logger.info(f"      Subject: {s['subject']}")
                logger.info(f"      Class: {s['class_name']}")
                logger.info(f"      Date: {s['date']}")
                logger.info(f"      Strand: {curr_row._mapping.get('strand_name')}")
                return session_data
        
        # No session with curriculum found, use first one anyway
        await db_gen.aclose()
        first = sessions[0]._mapping
        session_data = {
            "id": first["id"],
            "subject": first["subject"],
            "class_name": first["class_name"],
            "date": first["date"]
        }
        print_result(False, "No session with curriculum found, using first session (will skip)")
        logger.info(f"      Using: {first['subject']} - {first['class_name']} (Session {first['id']})")
        return session_data
        
    except Exception as e:
        print_result(False, f"Session finding failed: {e}")
        logger.error(traceback.format_exc())
        return None


async def test_curriculum_retrieval(session_data: dict):
    """Test 3: Test curriculum retrieval."""
    print_section("TEST 3: Curriculum Retrieval")
    
    if not session_data:
        print_result(False, "No session data provided")
        return None
    
    try:
        from slide_builder.slide_processor import get_curriculum_for_session
        
        curriculum = await get_curriculum_for_session(
            session_id=session_data["id"],
            teacher_id=UUID(TEST_TEACHER_ID),
            subject=session_data["subject"],
            class_name=session_data["class_name"]
        )
        
        if curriculum and curriculum.get("indicator_text"):
            print_result(True, "Curriculum retrieved successfully")
            logger.info(f"      Strand: {curriculum.get('strand_name')}")
            logger.info(f"      Substrand: {curriculum.get('substrand_name')}")
            logger.info(f"      Indicator: {curriculum.get('indicator_text', '')[:60]}...")
            return curriculum
        else:
            print_result(False, "No curriculum data found for session")
            return None
            
    except Exception as e:
        print_result(False, f"Curriculum retrieval failed: {e}")
        logger.error(traceback.format_exc())
        return None


async def test_rag_retrieval(session_data: dict, curriculum: dict):
    """Test 4: Test RAG retrieval."""
    print_section("TEST 4: RAG Retrieval")
    
    if not curriculum:
        print_result(False, "No curriculum data - skipping RAG test")
        return None
    
    try:
        from slide_builder.slide_retrieval import retrieve_all_pillars_for_slides, format_chunks_for_ai_prompt
        
        topic = curriculum.get("indicator_text") or f"{session_data['subject']} Lesson"
        
        logger.info(f"   Retrieving for topic: {topic[:60]}...")
        
        rag_chunks = await retrieve_all_pillars_for_slides(
            subject=session_data["subject"],
            class_name=session_data["class_name"],
            topic=topic,
            indicator_text=curriculum.get("indicator_text"),
            content_standard=curriculum.get("content_standard"),
            strand_name=curriculum.get("strand_name"),
            teacher_id=UUID(TEST_TEACHER_ID)
        )
        
        rag_content = format_chunks_for_ai_prompt(rag_chunks)
        
        print_result(True, f"RAG retrieval complete")
        logger.info(f"      Total chunks: {sum(len(v) for v in rag_chunks.values())}")
        logger.info(f"      Content length: {len(rag_content)} chars")
        
        return rag_content
        
    except Exception as e:
        print_result(False, f"RAG retrieval failed: {e}")
        logger.error(traceback.format_exc())
        return None


async def test_ai_generation(session_data: dict, curriculum: dict, rag_content: str):
    """Test 5: Test AI slide generation."""
    print_section("TEST 5: AI Slide Generation")
    
    if not curriculum:
        print_result(False, "No curriculum - skipping AI generation")
        return None
    
    try:
        from slide_builder.slide_processor import (
            build_enhanced_slide_prompt,
            call_ai_for_slides,
            get_education_context
        )
        
        # Get education context
        education_context = await get_education_context(
            UUID(TEST_TEACHER_ID),
            session_data["subject"],
            session_data["class_name"]
        )
        education_context["country"] = TEST_COUNTRY
        
        topic = curriculum.get("indicator_text") or f"{session_data['subject']} Lesson"
        if len(topic) > 100:
            topic = topic[:97] + "..."
        
        # Build prompt
        prompt = build_enhanced_slide_prompt(
            subject=session_data["subject"],
            class_level=session_data["class_name"],
            topic=topic,
            curriculum=curriculum,
            education_context=education_context,
            rag_content=rag_content or ""
        )
        
        logger.info(f"   Prompt length: {len(prompt)} chars")
        logger.info(f"   Calling Vertex AI...")
        
        # Generate slides
        slides_data = await call_ai_for_slides(prompt)
        
        if slides_data and "slides" in slides_data:
            num_slides = len(slides_data.get("slides", []))
            print_result(True, f"Generated {num_slides} slides")
            logger.info(f"      Topic: {slides_data.get('topic', 'N/A')}")
            return slides_data
        else:
            print_result(False, "AI returned invalid data")
            return None
            
    except Exception as e:
        error_msg = str(e)
        
        # Check for common authentication issues
        if "invalid_grant" in error_msg or "Invalid JWT" in error_msg:
            print_result(False, "AI generation failed: CREDENTIAL ERROR")
            logger.error("")
            logger.error("=" * 60)
            logger.error("GOOGLE CLOUD CREDENTIALS ISSUE DETECTED")
            logger.error("=" * 60)
            logger.error("The service account credentials are invalid or expired.")
            logger.error("")
            logger.error("To fix this:")
            logger.error("1. Go to Google Cloud Console → IAM & Admin → Service Accounts")
            logger.error("2. Find your Vertex AI service account")  
            logger.error("3. Click 'Keys' → 'Add Key' → 'Create new key' (JSON)")
            logger.error("4. Update GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI in your .env")
            logger.error("=" * 60)
        elif "ACCESS_TOKEN_EXPIRED" in error_msg:
            print_result(False, "AI generation failed: TOKEN EXPIRED")
            logger.error("Your access token has expired. Re-authenticate with 'gcloud auth login'")
        else:
            print_result(False, f"AI generation failed: {e}")
            logger.error(traceback.format_exc())
        return None


async def test_save_slide_deck(session_data: dict, curriculum: dict, slides_data: dict):
    """Test 6: Test saving slide deck."""
    print_section("TEST 6: Save Slide Deck")
    
    if not slides_data:
        print_result(False, "No slides data - skipping save")
        return None
    
    try:
        from slide_builder.slide_processor import save_slide_deck
        
        topic = curriculum.get("indicator_text") or f"{session_data['subject']} Lesson"
        if len(topic) > 100:
            topic = topic[:97] + "..."
        
        indicator_ids = []
        if curriculum.get("indicator_id"):
            indicator_ids.append(curriculum["indicator_id"])
        
        local_date = session_data.get("date") or date.today()
        if isinstance(local_date, str):
            local_date = date.fromisoformat(local_date)
        
        logger.info(f"   Saving to database...")
        
        slide_id = await save_slide_deck(
            teacher_id=UUID(TEST_TEACHER_ID),
            subject=session_data["subject"],
            class_name=session_data["class_name"],
            topic=topic,
            content_json=slides_data,
            indicator_ids=indicator_ids,
            local_date=local_date
        )
        
        if slide_id:
            print_result(True, f"Slide deck saved")
            logger.info(f"      Slide ID: {slide_id}")
            return slide_id
        else:
            print_result(False, "Failed to save slide deck")
            return None
            
    except Exception as e:
        print_result(False, f"Save failed: {e}")
        logger.error(traceback.format_exc())
        return None


async def test_save_image_prompts(slide_id: str, slides_data: dict):
    """Test 7: Test saving image prompts."""
    print_section("TEST 7: Save Image Prompts")
    
    if not slide_id:
        print_result(False, "No slide ID - skipping")
        return 0
    
    try:
        from slide_builder.slide_processor import save_image_prompts
        from slide_builder.slide_prompts import extract_image_prompts_from_slides
        
        image_prompts = extract_image_prompts_from_slides(slides_data)
        
        logger.info(f"   Found {len(image_prompts)} image prompts")
        
        if not image_prompts:
            print_result(True, "No images to save (expected for some slides)")
            return 0
        
        saved = await save_image_prompts(slide_id, image_prompts)
        
        print_result(True, f"Saved {saved} image prompts")
        return saved
        
    except Exception as e:
        print_result(False, f"Save image prompts failed: {e}")
        logger.error(traceback.format_exc())
        return 0


async def test_generate_images(slide_id: str):
    """Test 8: Test image generation."""
    print_section("TEST 8: Generate Images")
    
    if not slide_id:
        print_result(False, "No slide ID - skipping")
        return 0
    
    try:
        from slide_builder.image_generator import generate_images_for_slide
        
        logger.info(f"   Generating images for slide {slide_id}...")
        
        generated = await generate_images_for_slide(slide_id)
        
        print_result(True, f"Generated {generated} images")
        return generated
        
    except Exception as e:
        print_result(False, f"Image generation failed: {e}")
        logger.error(traceback.format_exc())
        return 0


async def verify_results(slide_id: str):
    """Verify final results in database."""
    print_section("VERIFICATION: Database Check")
    
    if not slide_id:
        print_result(False, "No slide ID to verify")
        return
    
    try:
        from database import get_db
        from sqlalchemy import text
        
        db_gen = get_db()
        db = await anext(db_gen)
        
        # Check slide
        result = await db.execute(
            text("""
                SELECT id, topic, generation_status,
                       jsonb_array_length(content_json->'slides') as slide_count
                FROM slides
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": slide_id}
        )
        slide = result.fetchone()
        
        if slide:
            m = slide._mapping
            logger.info(f"   ✅ Slide found:")
            logger.info(f"      ID: {m['id']}")
            logger.info(f"      Topic: {m['topic']}")
            logger.info(f"      Status: {m['generation_status']}")
            logger.info(f"      Slides: {m['slide_count']}")
        else:
            logger.warning(f"   ⚠️ Slide not found in database")
        
        # Check images
        img_result = await db.execute(
            text("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM slide_images
                WHERE slide_id = CAST(:id AS uuid)
            """),
            {"id": slide_id}
        )
        imgs = img_result.fetchone()
        
        if imgs:
            m = imgs._mapping
            logger.info(f"   📷 Images: {m['total']} total ({m['completed']} completed, {m['pending']} pending, {m['failed']} failed)")
        
        await db_gen.aclose()
        
    except Exception as e:
        print_result(False, f"Verification failed: {e}")
        logger.error(traceback.format_exc())


async def test_student_lesson_pack(slide_id: str, session_data: dict):
    """Test 9: Test Student Lesson Pack generation."""
    print_section("TEST 9: Student Lesson Pack Generation")
    
    if not slide_id:
        print_result(False, "No slide ID - skipping")
        return False
    
    try:
        from slide_builder.student_pack_generator import generate_student_pack
        
        logger.info(f"   Generating student lesson pack...")
        logger.info(f"      Slide ID: {slide_id}")
        logger.info(f"      Session ID: {session_data['id']}")
        logger.info(f"      Subject: {session_data['subject']}")
        logger.info(f"      Class: {session_data['class_name']}")
        
        pack_success = await generate_student_pack(
            slide_id=slide_id,
            session_id=str(session_data["id"]),
            teacher_id=TEST_TEACHER_ID,
            subject=session_data["subject"],
            class_name=session_data["class_name"]
        )
        
        if pack_success:
            print_result(True, "Student Lesson Pack created successfully")
            
            # Verify in database with detailed checks
            from database import get_db
            from sqlalchemy import text
            import json
            
            db_gen = get_db()
            db = await anext(db_gen)
            
            result = await db.execute(
                text("""
                    SELECT id, slide_id, session_id, status, 
                           simplified_notes, video_resources, podcast_audio_url,
                           content_json, created_at
                    FROM student_lesson_packs
                    WHERE slide_id = CAST(:slide_id AS uuid)
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"slide_id": slide_id}
            )
            pack = result.fetchone()
            
            if pack:
                m = pack._mapping
                logger.info(f"")
                logger.info(f"   📦 Pack Details:")
                logger.info(f"      Pack ID: {m['id']}")
                logger.info(f"      Session ID: {m['session_id']}")
                logger.info(f"      Status: {m['status']}")
                logger.info(f"")
                
                # Check legacy fields
                logger.info(f"   📝 Legacy Fields:")
                has_notes = bool(m.get('simplified_notes'))
                logger.info(f"      Simplified Notes: {'✅ Yes' if has_notes else '❌ No'}")
                
                # Parse video resources
                videos = []
                video_json = m.get('video_resources')
                if video_json:
                    if isinstance(video_json, str):
                        videos = json.loads(video_json)
                    else:
                        videos = video_json
                logger.info(f"      Video Resources: {len(videos)} videos")
                
                has_audio = bool(m.get('podcast_audio_url'))
                logger.info(f"      Podcast Audio: {'✅ Yes' if has_audio else '❌ No'}")
                if has_audio:
                    audio_url = m.get('podcast_audio_url')
                    logger.info(f"         URL: {audio_url[:80]}...")
                logger.info(f"")
                
                # Check structured content_json (NEW)
                content_json = m.get('content_json')
                if content_json:
                    if isinstance(content_json, str):
                        content = json.loads(content_json)
                    else:
                        content = content_json
                    
                    logger.info(f"   🎯 Structured Content (NEW):")
                    logger.info(f"      Pack ID: {content.get('pack_id', 'N/A')}")
                    logger.info(f"      Topic: {content.get('topic', 'N/A')}")
                    
                    slides = content.get('slides', [])
                    logger.info(f"      Total Slides: {len(slides)}")
                    
                    # List slide types
                    slide_types = [s.get('type') for s in slides]
                    logger.info(f"      Slide Types: {slide_types}")
                    
                    # Check summary
                    summary = content.get('summary', {})
                    if summary:
                        logger.info(f"")
                        logger.info(f"   📊 Summary:")
                        logger.info(f"      Has Notes: {summary.get('has_notes', False)}")
                        logger.info(f"      Video Count: {summary.get('video_count', 0)}")
                        logger.info(f"      Has Podcast: {summary.get('has_podcast', False)}")
                        
                        duration_ms = summary.get('podcast_duration_ms', 0)
                        duration_min = duration_ms / 60000 if duration_ms else 0
                        logger.info(f"      Podcast Duration: {duration_min:.1f} minutes")
                        
                        logger.info(f"      MCQ Count: {summary.get('mcq_count', 0)}")
                        logger.info(f"      Essay Count: {summary.get('essay_count', 0)}")
                    
                    # Verify answer keys are at end
                    logger.info(f"")
                    logger.info(f"   🔑 Assessment Verification:")
                    has_mcq_assessment = 'assessment_mcq' in slide_types
                    has_essay_assessment = 'assessment_essay' in slide_types
                    has_mcq_answers = 'answer_key_mcq' in slide_types
                    has_essay_answers = 'answer_key_essay' in slide_types
                    
                    logger.info(f"      MCQ Assessment: {'✅' if has_mcq_assessment else '❌'}")
                    logger.info(f"      Essay Assessment: {'✅' if has_essay_assessment else '❌'}")
                    logger.info(f"      MCQ Answer Key: {'✅' if has_mcq_answers else '❌'}")
                    logger.info(f"      Essay Answer Key: {'✅' if has_essay_answers else '❌'}")
                    
                    # Verify answer keys are at the end
                    if has_mcq_answers or has_essay_answers:
                        answer_key_types = ['answer_key_mcq', 'answer_key_essay']
                        answer_slides = [s for s in slides if s.get('type') in answer_key_types]
                        if answer_slides:
                            # Check if answer slides are at the end
                            last_answer_idx = max([slides.index(s) for s in answer_slides])
                            is_at_end = last_answer_idx >= len(slides) - len(answer_slides)
                            logger.info(f"      Answer Keys at End: {'✅' if is_at_end else '⚠️ No'}")
                    
                    # Verify assessments don't have answers
                    logger.info(f"")
                    logger.info(f"   🔒 Security Check (Assessments):")
                    assessment_slides = [s for s in slides if s.get('type') in ['assessment_mcq', 'assessment_essay']]
                    all_secure = True
                    for slide in assessment_slides:
                        content_data = slide.get('content', {})
                        questions = content_data.get('questions', [])
                        
                        if slide.get('type') == 'assessment_mcq':
                            # Check MCQ questions don't have correct_answer
                            for q in questions:
                                if 'correct_answer' in q or 'explanation' in q:
                                    all_secure = False
                                    logger.warning(f"         ⚠️ MCQ question has answer!")
                        
                        elif slide.get('type') == 'assessment_essay':
                            # Check essay questions don't have key_points
                            for q in questions:
                                if 'key_points' in q:
                                    all_secure = False
                                    logger.warning(f"         ⚠️ Essay question has key points!")
                    
                    if all_secure:
                        logger.info(f"      Assessments Secure: ✅ (No answers in questions)")
                    else:
                        logger.info(f"      Assessments Secure: ❌ (Found answers in questions!)")
                    
                else:
                    logger.warning(f"   ⚠️ No structured content_json found")
                
                # Overall result
                logger.info(f"")
                if m['status'] == 'completed':
                    print_result(True, "All verifications passed!")
                    await db_gen.aclose()
                    return True
                else:
                    print_result(False, f"Pack status is {m.get('status', 'unknown')}")
                    await db_gen.aclose()
                    return False
            else:
                await db_gen.aclose()
                print_result(False, "Student Lesson Pack not found in database")
                return False

            
    except ImportError as e:
        print_result(False, f"Student pack module not available: {e}")
        logger.error(traceback.format_exc())
        return False
    except Exception as e:
        print_result(False, f"Student Lesson Pack failed: {e}")
        logger.error(traceback.format_exc())
        return False


async def cleanup_test_data(slide_id: str):
    """Optional: Clean up test data."""
    if not slide_id:
        return
    
    # Uncomment to enable cleanup
    # print_section("CLEANUP")
    # try:
    #     from database import get_db
    #     from sqlalchemy import text
    #     
    #     db_gen = get_db()
    #     db = await anext(db_gen)
    #     
    #     await db.execute(
    #         text("DELETE FROM slide_images WHERE slide_id = CAST(:id AS uuid)"),
    #         {"id": slide_id}
    #     )
    #     await db.execute(
    #         text("DELETE FROM slides WHERE id = CAST(:id AS uuid)"),
    #         {"id": slide_id}
    #     )
    #     await db.commit()
    #     await db_gen.aclose()
    #     
    #     print_result(True, "Test data cleaned up")
    # except Exception as e:
    #     print_result(False, f"Cleanup failed: {e}")


async def main():
    """Run all tests."""
    print_section("SLIDE GENERATION COMPLETE FLOW TEST")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Teacher: {TEST_TEACHER_ID}")
    logger.info("")
    
    start_time = datetime.now()
    results = {
        "db": False,
        "session": None,
        "curriculum": None,
        "rag": None,
        "ai": None,
        "save": None,
        "images_saved": 0,
        "images_generated": 0,
        "student_pack": False
    }
    
    # Test 1: Database
    results["db"] = await test_database_connection()
    if not results["db"]:
        logger.error("Database connection failed - cannot continue")
        return
    
    # Test 2: Find session
    results["session"] = await test_find_session()
    if not results["session"]:
        logger.error("No session found - cannot continue")
        return
    
    # Test 3: Curriculum
    results["curriculum"] = await test_curriculum_retrieval(results["session"])
    # Continue even if no curriculum (will skip later)
    
    # Test 4: RAG
    results["rag"] = await test_rag_retrieval(results["session"], results["curriculum"])
    
    # Test 5: AI Generation
    results["ai"] = await test_ai_generation(
        results["session"],
        results["curriculum"],
        results["rag"]
    )
    
    # Test 6: Save Slide Deck
    results["save"] = await test_save_slide_deck(
        results["session"],
        results["curriculum"],
        results["ai"]
    )
    
    # Test 7: Save Image Prompts
    results["images_saved"] = await test_save_image_prompts(
        results["save"],
        results["ai"]
    )
    
    # Test 8: Generate Images
    results["images_generated"] = await test_generate_images(results["save"])
    
    # Test 9: Student Lesson Pack
    results["student_pack"] = await test_student_lesson_pack(
        results["save"],
        results["session"]
    )
    
    # Verification
    await verify_results(results["save"])
    
    # Summary
    print_section("TEST SUMMARY")
    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"   Total time: {elapsed:.1f} seconds")
    logger.info("")
    logger.info("   Results:")
    logger.info(f"   • Database connection: {'✅' if results['db'] else '❌'}")
    logger.info(f"   • Session found: {'✅' if results['session'] else '❌'}")
    logger.info(f"   • Curriculum: {'✅' if results['curriculum'] else '⚠️ (not required)'}")
    logger.info(f"   • RAG retrieval: {'✅' if results['rag'] else '⚠️'}")
    logger.info(f"   • AI generation: {'✅' if results['ai'] else '❌'}")
    logger.info(f"   • Slide saved: {'✅' if results['save'] else '❌'}")
    logger.info(f"   • Images saved: {results['images_saved']}")
    logger.info(f"   • Images generated: {results['images_generated']}")
    logger.info(f"   • Student pack: {'✅' if results['student_pack'] else '⚠️'}")
    logger.info("")
    
    if results["save"]:
        logger.info(f"   🎉 SUCCESS! Slide ID: {results['save']}")
    else:
        logger.info("   ⚠️ Test completed with issues - check logs above")
    
    # Cleanup (optional)
    # await cleanup_test_data(results["save"])


if __name__ == "__main__":
    asyncio.run(main())
