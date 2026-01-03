import asyncio
from database import get_db
from sqlalchemy import text

async def check():
    db_gen = get_db()
    db = await anext(db_gen)
    result = await db.execute(
        text("""
            SELECT id, teacher_id, subject, class_name, session_date, session_id, previous_session_id, generated_at 
            FROM lesson_briefs 
            ORDER BY generated_at DESC 
            LIMIT 5
        """)
    )
    rows = result.fetchall()
    print("\nRecent lesson briefs:")
    print("-" * 100)
    for row in rows:
        r = dict(row._mapping)
        print(f"Subject: {r['subject']}, Class: {r['class_name']}")
        print(f"  Session Date: {r['session_date']}, Session ID: {r['session_id']}")
        print(f"  Previous Session ID: {r['previous_session_id']}")
        print(f"  Generated At: {r['generated_at']}")
        print("-" * 100)
    await db_gen.aclose()

asyncio.run(check())
