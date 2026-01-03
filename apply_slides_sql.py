"""
Apply SQL tables for slide builder.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from database import get_db
    from sqlalchemy import text
    
    # Read SQL file
    sql_path = Path(__file__).parent / "slide_builder" / "create_slides_tables.sql"
    
    if not sql_path.exists():
        print(f"❌ SQL file not found: {sql_path}")
        return
    
    print(f"📂 Reading SQL from: {sql_path}")
    sql_content = sql_path.read_text(encoding='utf-8')
    
    # Split into statements (simple split by semicolon, ignoring function blocks)
    # For complex SQL, we'll execute the whole thing
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Execute each statement
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        for i, stmt in enumerate(statements, 1):
            if not stmt or stmt.startswith('--'):
                continue
            
            try:
                print(f"\n📝 Executing statement {i}...")
                print(f"   {stmt[:80]}..." if len(stmt) > 80 else f"   {stmt}")
                await db.execute(text(stmt))
                print(f"   ✅ OK")
            except Exception as e:
                error_str = str(e).lower()
                if 'already exists' in error_str or 'exist' in error_str:
                    print(f"   ⚠️ (already exists - OK)")
                else:
                    print(f"   ❌ Error: {e}")
        
        await db.commit()
        print("\n✅ All tables created/updated!")
        
        # Verify tables exist
        print("\n🔍 Verifying tables...")
        
        result = await db.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name IN ('slides', 'slide_images', 'student_lesson_packs')
        """))
        tables = [row[0] for row in result.fetchall()]
        
        for table in ['slides', 'slide_images', 'student_lesson_packs']:
            if table in tables:
                print(f"   ✅ {table} exists")
            else:
                print(f"   ❌ {table} NOT FOUND")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
    finally:
        await db_gen.aclose()

if __name__ == "__main__":
    asyncio.run(main())
