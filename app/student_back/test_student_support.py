"""
Student Support Pack - Test Script

This script tests the student support pack generation flow by:
1. Creating a pack via the API
2. Starting the background workers
3. Monitoring until completion
4. Fetching the generated pack

Usage:
    python student_back/test_student_support.py
"""

import asyncio
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy import text


async def test_student_support_flow():
    """Test the complete student support pack generation flow."""
    
    print("=" * 70)
    print("STUDENT SUPPORT PACK - TEST SCRIPT")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Import after adding to path
    from app.core.database import get_db
    from app.student_back.worker import start_workers, stop_workers
    
    # Test data
    TEST_TEACHER_ID = None  # Will be fetched from DB
    test_data = {
        "student_name": "Test Student",
        "subject": "Science",
        "class_name": "Basic 8",
        "topic": "The Water Cycle",
        "interests": ["football", "video games", "music"],
        "health_considerations": "Student has ADHD - needs frequent breaks and visual aids. Prefers hands-on activities.",
        "edu_sys": "Ghana Education Service",
        "edu_lvl": "JHS"
    }
    
    print("\n📋 TEST DATA:")
    print(f"   Student: {test_data['student_name']}")
    print(f"   Subject: {test_data['subject']}")
    print(f"   Class: {test_data['class_name']}")
    print(f"   Topic: {test_data['topic']}")
    print(f"   Interests: {', '.join(test_data['interests'])}")
    print(f"   Considerations: {test_data['health_considerations'][:50]}...")
    print()
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Step 1: Get a teacher ID from the database
        print("🔍 STEP 1: Finding a teacher in the database...")
        result = await db.execute(text("SELECT id FROM teacherprofile LIMIT 1"))
        row = result.fetchone()
        
        if not row:
            print("❌ ERROR: No teachers found in database. Please create a teacher first.")
            return False
        
        TEST_TEACHER_ID = str(row[0])
        print(f"   ✓ Found teacher: {TEST_TEACHER_ID}")
        
        # Step 2: Create a test pack in the database
        print("\n📝 STEP 2: Creating test pack in database...")
        
        insert_result = await db.execute(
            text("""
                INSERT INTO student_support_packs (
                    teacher_id, student_name, subject, class_name,
                    edu_sys, edu_lvl, topic, interests, health_considerations,
                    status, created_at, updated_at
                ) VALUES (
                    CAST(:teacher_id AS uuid), :student_name, :subject, :class_name,
                    :edu_sys, :edu_lvl, :topic, CAST(:interests AS jsonb), :health_considerations,
                    'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING id
            """),
            {
                "teacher_id": TEST_TEACHER_ID,
                "student_name": test_data["student_name"],
                "subject": test_data["subject"],
                "class_name": test_data["class_name"],
                "edu_sys": test_data["edu_sys"],
                "edu_lvl": test_data["edu_lvl"],
                "topic": test_data["topic"],
                "interests": json.dumps(test_data["interests"]),
                "health_considerations": test_data["health_considerations"]
            }
        )
        pack_id = str(insert_result.fetchone()[0])
        await db.commit()
        print(f"   ✓ Created pack: {pack_id}")
        
        # Step 3: Start the workers
        print("\n🚀 STEP 3: Starting background workers...")
        await start_workers()
        print("   ✓ Workers started (2 workers)")
        
        # Step 4: Monitor progress
        print("\n⏳ STEP 4: Monitoring generation progress...")
        max_wait = 180  # 3 minutes max
        elapsed = 0
        poll_interval = 5
        
        while elapsed < max_wait:
            result = await db.execute(
                text("SELECT status FROM student_support_packs WHERE id = CAST(:id AS uuid)"),
                {"id": pack_id}
            )
            row = result.fetchone()
            status = row[0] if row else "unknown"
            
            print(f"   [{elapsed}s] Status: {status}")
            
            if status == "completed":
                print("\n   ✓ Pack generation completed!")
                break
            elif status == "failed":
                print("\n   ❌ Pack generation failed!")
                break
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        # Step 5: Stop workers
        print("\n🛑 STEP 5: Stopping workers...")
        await stop_workers()
        print("   ✓ Workers stopped")
        
        # Step 6: Fetch and display results
        print("\n📊 STEP 6: Fetching generated pack...")
        result = await db.execute(
            text("""
                SELECT id, student_name, subject, topic, status, 
                       teacher_instructions, content_json
                FROM student_support_packs 
                WHERE id = CAST(:id AS uuid)
            """),
            {"id": pack_id}
        )
        row = result.fetchone()
        
        if row:
            content_json = row._mapping.get("content_json") or {}
            summary = content_json.get("summary", {})
            
            print("\n" + "=" * 70)
            print("📋 RESULT SUMMARY")
            print("=" * 70)
            print(f"   Pack ID: {row._mapping['id']}")
            print(f"   Student: {row._mapping['student_name']}")
            print(f"   Subject: {row._mapping['subject']}")
            print(f"   Topic: {row._mapping['topic']}")
            print(f"   Status: {row._mapping['status']}")
            print(f"   Total Slides: {summary.get('total_slides', 0)}")
            print(f"   Has Notes: {summary.get('has_notes', False)}")
            print(f"   Image Count: {summary.get('image_count', 0)}")
            print(f"   Has Teacher Instructions: {summary.get('has_teacher_instructions', False)}")
            print(f"   MCQ Count: {summary.get('mcq_count', 0)}")
            print(f"   Essay Count: {summary.get('essay_count', 0)}")
            
            if row._mapping.get("teacher_instructions"):
                print("\n📖 TEACHER INSTRUCTIONS (first 500 chars):")
                print("-" * 40)
                print(row._mapping["teacher_instructions"][:500])
            
            # List slides
            slides = content_json.get("slides", [])
            if slides:
                print(f"\n📑 SLIDES ({len(slides)} total):")
                print("-" * 40)
                for slide in slides:
                    print(f"   [{slide.get('id')}] {slide.get('type')} - {slide.get('content', {}).get('title', 'No title')}")
            
            print("\n" + "=" * 70)
            print(f"✅ TEST COMPLETED SUCCESSFULLY at {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 70)
            
            return row._mapping['status'] == 'completed'
        else:
            print("❌ Pack not found in database!")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db_gen.aclose()


if __name__ == "__main__":
    success = asyncio.run(test_student_support_flow())
    sys.exit(0 if success else 1)
