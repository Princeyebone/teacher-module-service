import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db
from sqlalchemy import text

async def drop_constraint():
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        await db.execute(text("""
            ALTER TABLE slides 
            DROP CONSTRAINT IF EXISTS unique_slide_per_teacher_subject_class_topic
        """))
        await db.commit()
        print("✅ Constraint dropped successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await db_gen.aclose()

if __name__ == "__main__":
    asyncio.run(drop_constraint())
