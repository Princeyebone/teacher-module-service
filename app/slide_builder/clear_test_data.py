"""
Clear test data from slides and student_lesson_packs tables.
Run before test_complete_flow.py to ensure clean state.

Usage: python slide_builder/clear_test_data.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from sqlalchemy import text

TEST_TEACHER_ID = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"


async def clear_test_data():
    """Clear test data for the test teacher."""
    print("=" * 70)
    print("  CLEARING TEST DATA")
    print("=" * 70)
    print(f"Teacher ID: {TEST_TEACHER_ID}")
    print()
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Count before deletion
        result = await db.execute(
            text("SELECT COUNT(*) as count FROM slides WHERE teacher_id = CAST(:tid AS uuid)"),
            {"tid": TEST_TEACHER_ID}
        )
        slides_count = result.fetchone()._mapping['count']
        
        result = await db.execute(
            text("SELECT COUNT(*) as count FROM student_lesson_packs WHERE teacher_id = CAST(:tid AS uuid)"),
            {"tid": TEST_TEACHER_ID}
        )
        packs_count = result.fetchone()._mapping['count']
        
        result = await db.execute(
            text("""
                SELECT COUNT(*) as count FROM slide_images 
                WHERE slide_id IN (
                    SELECT id FROM slides WHERE teacher_id = CAST(:tid AS uuid)
                )
            """),
            {"tid": TEST_TEACHER_ID}
        )
        images_count = result.fetchone()._mapping['count']
        
        print(f"Found:")
        print(f"  - {slides_count} slides")
        print(f"  - {packs_count} student packs")
        print(f"  - {images_count} slide images")
        print()
        
        if slides_count == 0 and packs_count == 0 and images_count == 0:
            print("✅ No test data to clear")
            return
        
        # Delete in correct order (foreign key constraints)
        print("Deleting...")
        
        # 1. Delete student packs
        if packs_count > 0:
            await db.execute(
                text("DELETE FROM student_lesson_packs WHERE teacher_id = CAST(:tid AS uuid)"),
                {"tid": TEST_TEACHER_ID}
            )
            print(f"  ✅ Deleted {packs_count} student packs")
        
        # 2. Delete slide images
        if images_count > 0:
            await db.execute(
                text("""
                    DELETE FROM slide_images 
                    WHERE slide_id IN (
                        SELECT id FROM slides WHERE teacher_id = CAST(:tid AS uuid)
                    )
                """),
                {"tid": TEST_TEACHER_ID}
            )
            print(f"  ✅ Deleted {images_count} slide images")
        
        # 3. Delete slides
        if slides_count > 0:
            await db.execute(
                text("DELETE FROM slides WHERE teacher_id = CAST(:tid AS uuid)"),
                {"tid": TEST_TEACHER_ID}
            )
            print(f"  ✅ Deleted {slides_count} slides")
        
        await db.commit()
        
        print()
        print("=" * 70)
        print("  ✅ TEST DATA CLEARED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("You can now run: python slide_builder/test_complete_flow.py")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
    finally:
        await db_gen.aclose()


if __name__ == "__main__":
    asyncio.run(clear_test_data())
