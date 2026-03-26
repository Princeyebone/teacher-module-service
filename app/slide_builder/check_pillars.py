import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import get_db
from sqlalchemy import text

async def check_pillars():
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        result = await db.execute(text("""
            SELECT DISTINCT pillar, COUNT(*) as cnt 
            FROM knowledgemetadata 
            GROUP BY pillar 
            ORDER BY cnt DESC
        """))
        rows = result.fetchall()
        
        with open("slide_builder/pillars.txt", "w", encoding="utf-8") as f:
            f.write("KNOWLEDGE PILLARS IN DATABASE:\n")
            for row in rows:
                pillar = row._mapping['pillar'] or 'NULL'
                cnt = row._mapping['cnt']
                f.write(f"'{pillar}': {cnt} records\n")
            
    finally:
        await db_gen.aclose()

if __name__ == "__main__":
    asyncio.run(check_pillars())
