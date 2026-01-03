"""Check the weekly_lesson_notes table to verify data was saved correctly."""
import asyncio
from database import get_db
from sqlalchemy import text

async def check():
    db_gen = get_db()
    db = await anext(db_gen)
    
    result = await db.execute(
        text("""
            SELECT id, subject, class_name, indicator_code, week_date, 
                   LEFT(performance_indicator, 100) as perf_ind,
                   LEFT(phase1_activity, 100) as p1_activity,
                   generated_at
            FROM weekly_lesson_notes 
            ORDER BY generated_at DESC 
            LIMIT 10
        """)
    )
    
    print("\n=== Recent Weekly Lesson Notes ===\n")
    rows = result.fetchall()
    
    for row in rows:
        r = dict(row._mapping)
        print(f"📚 {r['subject']} - {r['class_name']}")
        print(f"   Indicator: {r['indicator_code']} | Week: {r['week_date']}")
        print(f"   Generated: {r['generated_at']}")
        print(f"   Performance: {r['perf_ind']}...")
        print(f"   Phase 1: {r['p1_activity']}...")
        print("-" * 60)
    
    print(f"\n✅ Total records shown: {len(rows)}")
    await db_gen.aclose()

asyncio.run(check())
