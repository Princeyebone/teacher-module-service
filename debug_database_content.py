#!/usr/bin/env python3
"""
Debug script to check if there's data in the database tables
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select, text
from uuid import UUID
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import configuration
try:
    from config import settings
    from database import async_engine
    from model import Strand, Substrand, ContentStandard, Indicator
    print("✅ Successfully imported all modules")
except Exception as e:
    print(f"❌ Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_database_content():
    """Debug the database content to see if there's data in the tables"""
    print("=== DEBUGGING DATABASE CONTENT ===")
    
    try:
        # Test database connection
        print("1. Testing database connection...")
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Database connection successful: {version}")
        
        # Create a session
        print("\n2. Creating database session...")
        from sqlalchemy.ext.asyncio import AsyncSession
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Check if we can query the tables
            print("\n3. Checking Strand table...")
            try:
                strand_count = await session.execute(select(Strand))
                strands = strand_count.scalars().all()
                print(f"✅ Strand table accessible, found {len(strands)} records")
                if strands:
                    print("   First few strand records:")
                    for i, strand in enumerate(strands[:3]):
                        print(f"     {i+1}. {strand.strand_name} - {strand.subject} - Week {strand.week_number}")
                else:
                    print("   No strand records found")
            except Exception as e:
                print(f"❌ Error querying Strand table: {e}")
            
            print("\n4. Checking Substrand table...")
            try:
                substrand_count = await session.execute(select(Substrand))
                substrands = substrand_count.scalars().all()
                print(f"✅ Substrand table accessible, found {len(substrands)} records")
                if substrands:
                    print("   First few substrand records:")
                    for i, substrand in enumerate(substrands[:3]):
                        print(f"     {i+1}. {substrand.substrand_name} - Strand ID {substrand.strand_id}")
                else:
                    print("   No substrand records found")
            except Exception as e:
                print(f"❌ Error querying Substrand table: {e}")
            
            print("\n5. Checking ContentStandard table...")
            try:
                cs_count = await session.execute(select(ContentStandard))
                content_standards = cs_count.scalars().all()
                print(f"✅ ContentStandard table accessible, found {len(content_standards)} records")
                if content_standards:
                    print("   First few content standard records:")
                    for i, cs in enumerate(content_standards[:3]):
                        print(f"     {i+1}. {cs.content_standard_code or 'No Code'} - {cs.content_standard[:50]}...")
                else:
                    print("   No content standard records found")
            except Exception as e:
                print(f"❌ Error querying ContentStandard table: {e}")
            
            print("\n6. Checking Indicator table...")
            try:
                indicator_count = await session.execute(select(Indicator))
                indicators = indicator_count.scalars().all()
                print(f"✅ Indicator table accessible, found {len(indicators)} records")
                if indicators:
                    print("   First few indicator records:")
                    for i, indicator in enumerate(indicators[:3]):
                        print(f"     {i+1}. {indicator.indicator_code or 'No Code'} - {indicator.indicator_text[:50]}...")
                else:
                    print("   No indicator records found")
            except Exception as e:
                print(f"❌ Error querying Indicator table: {e}")
            
            # Check if there are any teachers in the database
            print("\n7. Checking TeacherProfile table...")
            try:
                from model import TeacherProfile
                teacher_count = await session.execute(select(TeacherProfile))
                teachers = teacher_count.scalars().all()
                print(f"✅ TeacherProfile table accessible, found {len(teachers)} records")
                if teachers:
                    print("   First few teacher records:")
                    for i, teacher in enumerate(teachers[:3]):
                        print(f"     {i+1}. ID: {teacher.id} - Name: {teacher.display_name}")
                else:
                    print("   No teacher records found")
            except Exception as e:
                print(f"❌ Error querying TeacherProfile table: {e}")
            
        print("\n=== DEBUGGING COMPLETE ===")
        
    except Exception as e:
        print(f"❌ Debugging failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(debug_database_content())