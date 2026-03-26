"""Check database connection and list tables."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from app.core.database import get_db
    from sqlalchemy import text
    from app.core.config import settings
    
    output = []
    output.append(f"Database URL: {settings.DATABASE_URL[:80]}...")
    output.append("")
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    # Check current database
    result = await db.execute(text("SELECT current_database(), current_user, current_schema()"))
    row = result.fetchone()
    output.append(f"Current database: {row[0]}")
    output.append(f"Current user: {row[1]}")
    output.append(f"Current schema: {row[2]}")
    output.append("")
    
    # List all tables
    result = await db.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """))
    tables = [row[0] for row in result.fetchall()]
    
    output.append(f"Tables in public schema ({len(tables)} total):")
    for t in tables:
        output.append(f"  - {t}")
    
    # Check for specific tables
    output.append("\n🔍 Checking specific tables:")
    for table in ['slides', 'slide_images', 'knowledgeembedding', 'knowledgemetadata', 'student_lesson_packs']:
        if table in tables:
            output.append(f"  ✅ {table} exists")
        else:
            output.append(f"  ❌ {table} NOT FOUND")
    
    await db_gen.aclose()
    
    # Write to file
    with open("db_check_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    
    print("Results written to db_check_results.txt")

if __name__ == "__main__":
    asyncio.run(main())
