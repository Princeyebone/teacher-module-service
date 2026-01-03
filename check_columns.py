import asyncio
from database import get_db
from sqlalchemy import text

async def main():
    db_gen = get_db()
    db = await anext(db_gen)
    
    # Check weeklytimetable columns
    r = await db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'weeklytimetable'"))
    print("weeklytimetable columns:")
    for row in r.fetchall():
        print(f"  - {row[0]}")
    
    await db_gen.aclose()

asyncio.run(main())
