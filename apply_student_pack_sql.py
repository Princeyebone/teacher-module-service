import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.ERROR)
from database import get_db
from sqlalchemy import text

async def apply_sql():
    print("Applying SQL...")
    sql_path = Path('slide_builder/create_student_pack_table.sql')
    if not sql_path.exists():
        print("SQL file not found")
        return

    with open(sql_path, 'r') as f:
        sql = f.read()
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Split statements
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        
        for statement in statements:
            print(f"Executing: {statement[:50]}...")
            await db.execute(text(statement))
            
        await db.commit()
        print("✅ Tables created successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")
        with open("sql_error.txt", "w") as err_file:
            err_file.write(str(e))
        import traceback
        traceback.print_exc()
    finally:
        await db_gen.aclose()

if __name__ == "__main__":
    asyncio.run(apply_sql())
