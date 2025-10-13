#!/usr/bin/env python3
"""
Check TempExtract data in the database.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from model import TempExtract

async def check_temp_extract():
    """Check TempExtract data in the database."""
    print("Checking TempExtract data in the database...")
    
    try:
        # Create async engine
        async_engine = create_async_engine(settings.DATABASE_URL)
        
        # Create database session
        async with AsyncSession(async_engine) as session:
            # Get all TempExtract entries
            result = await session.execute(select(TempExtract))
            entries = result.scalars().all()
            
            print(f"Total TempExtract entries: {len(entries)}")
            
            for entry in entries:
                print(f"  ID: {entry.id}")
                print(f"    Teacher: {entry.teacher_id}")
                print(f"    Subject: {entry.subject}")
                print(f"    Class: {entry.class_name}")
                print(f"    Type: {entry.type}")
                print(f"    Updated: {entry.updated_at}")
                print(f"    Data present: {entry.data is not None}")
                if entry.data:
                    print(f"    Data type: {type(entry.data)}")
                    if isinstance(entry.data, dict):
                        print(f"    Data keys: {list(entry.data.keys()) if entry.data else 'None'}")
                    elif isinstance(entry.data, list):
                        print(f"    Data length: {len(entry.data)}")
                print()
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_temp_extract())