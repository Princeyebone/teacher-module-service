import asyncio
import os
import sys

# Add current dir to path
sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from config import settings

async def check():
    url = settings.DATABASE_URL
    # Ensure asyncio compatible driver if needed (postgresql:// -> postgresql+asyncpg://) - but let's trust the env var or user setting is correct for existing code
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT podcast_audio_url, status FROM student_lesson_packs ORDER BY updated_at DESC LIMIT 1"))
            row = result.fetchone()
            if row:
                print(f"LATEST PACK STATUS: {row[1]}")
                print(f"LATEST AUDIO URL: {row[0]}")
            else:
                print("No packs found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
