#!/usr/bin/env python3
"""
Debug script to check what teacher IDs are actually in the data
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select, distinct
from uuid import UUID
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import configuration
try:
    from config import settings
    from database import async_engine
    from model import Strand, Substrand, ContentStandard, Indicator, TeacherProfile
    print("✅ Successfully imported all modules")
except Exception as e:
    print(f"❌ Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_actual_teacher_ids():
    """Debug what teacher IDs are actually in the data"""
    print("=== DEBUGGING ACTUAL TEACHER IDS IN DATA ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        from sqlalchemy.ext.asyncio import AsyncSession
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Get distinct teacher IDs from each table
            print("\n2. Getting distinct teacher IDs from Strand table...")
            strand_teachers = await session.execute(select(distinct(Strand.teacher_id)))
            strand_teacher_ids = strand_teachers.scalars().all()
            print(f"   ✅ Found {len(strand_teacher_ids)} distinct teacher IDs in Strand table:")
            for tid in strand_teacher_ids:
                print(f"      - {tid}")
            
            print("\n3. Getting distinct teacher IDs from Substrand table...")
            substrand_teachers = await session.execute(select(distinct(Substrand.teacher_id)))
            substrand_teacher_ids = substrand_teachers.scalars().all()
            print(f"   ✅ Found {len(substrand_teacher_ids)} distinct teacher IDs in Substrand table:")
            for tid in substrand_teacher_ids:
                print(f"      - {tid}")
            
            print("\n4. Getting distinct teacher IDs from ContentStandard table...")
            cs_teachers = await session.execute(select(distinct(ContentStandard.teacher_id)))
            cs_teacher_ids = cs_teachers.scalars().all()
            print(f"   ✅ Found {len(cs_teacher_ids)} distinct teacher IDs in ContentStandard table:")
            for tid in cs_teacher_ids:
                print(f"      - {tid}")
            
            print("\n5. Getting distinct teacher IDs from Indicator table...")
            indicator_teachers = await session.execute(select(distinct(Indicator.teacher_id)))
            indicator_teacher_ids = indicator_teachers.scalars().all()
            print(f"   ✅ Found {len(indicator_teacher_ids)} distinct teacher IDs in Indicator table:")
            for tid in indicator_teacher_ids:
                print(f"      - {tid}")
            
            # Check if any of these teacher IDs match our actual teachers
            print("\n6. Getting all teacher IDs from TeacherProfile table...")
            teacher_result = await session.execute(select(TeacherProfile.id))
            teacher_ids = teacher_result.scalars().all()
            print(f"   ✅ Found {len(teacher_ids)} teacher IDs in TeacherProfile table:")
            for tid in teacher_ids:
                print(f"      - {tid}")
            
            # Check for matches
            print("\n7. Checking for matches between data and teacher profiles...")
            strand_matches = set(strand_teacher_ids) & set(teacher_ids)
            substrand_matches = set(substrand_teacher_ids) & set(teacher_ids)
            cs_matches = set(cs_teacher_ids) & set(teacher_ids)
            indicator_matches = set(indicator_teacher_ids) & set(teacher_ids)
            
            print(f"   Strand matches: {len(strand_matches)}")
            print(f"   Substrand matches: {len(substrand_matches)}")
            print(f"   ContentStandard matches: {len(cs_matches)}")
            print(f"   Indicator matches: {len(indicator_matches)}")
            
            # Check what teacher IDs are in the data but not in TeacherProfile
            strand_orphans = set(strand_teacher_ids) - set(teacher_ids)
            substrand_orphans = set(substrand_teacher_ids) - set(teacher_ids)
            cs_orphans = set(cs_teacher_ids) - set(teacher_ids)
            indicator_orphans = set(indicator_teacher_ids) - set(teacher_ids)
            
            print(f"\n8. Orphaned teacher IDs (in data but not in TeacherProfile):")
            print(f"   Strand orphans: {strand_orphans}")
            print(f"   Substrand orphans: {substrand_orphans}")
            print(f"   ContentStandard orphans: {cs_orphans}")
            print(f"   Indicator orphans: {indicator_orphans}")
            
        print("\n=== DEBUGGING COMPLETE ===")
        
    except Exception as e:
        print(f"❌ Debugging failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(debug_actual_teacher_ids())