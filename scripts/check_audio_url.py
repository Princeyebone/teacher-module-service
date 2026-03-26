
import asyncio
import logging
from app.core.database import get_db
from sqlalchemy import text

logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

async def check_audio():
    async for db in get_db():
        print("Checking by Pack ID...")
        result = await db.execute(
            text("SELECT podcast_audio_url, status FROM student_lesson_packs WHERE id = '743ef846-a7d4-4a3e-8116-eccb2f3938de'")
        )
        row = result.fetchone()
        if row:
            print(f"✅ Found! URL: {row[0]}")
            print(f"Status: {row[1]}")
        else:
            print("❌ No row found by Pack ID")
        
        break

if __name__ == "__main__":
    asyncio.run(check_audio())
