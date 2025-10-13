#!/usr/bin/env python3
"""
Debug script to check teacher ID filtering in the endpoints
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select
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

async def debug_teacher_filtering():
    """Debug the teacher ID filtering in the endpoints"""
    print("=== DEBUGGING TEACHER ID FILTERING ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        from sqlalchemy.ext.asyncio import AsyncSession
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Get all teachers to see what IDs we have
            print("\n2. Getting all teachers...")
            teacher_result = await session.execute(select(TeacherProfile))
            teachers = teacher_result.scalars().all()
            print(f"✅ Found {len(teachers)} teachers")
            
            # Display teacher information
            for i, teacher in enumerate(teachers):
                print(f"   {i+1}. ID: {teacher.id} - Name: {teacher.display_name} - Role: {teacher.role}")
            
            # If we have teachers, test filtering by each teacher ID
            if teachers:
                for teacher in teachers[:2]:  # Test with first 2 teachers
                    print(f"\n3. Testing queries for teacher ID: {teacher.id}")
                    
                    # Test Strand query with teacher ID
                    print("   Testing Strand query...")
                    strand_query = select(Strand).where(Strand.teacher_id == teacher.id)
                    strand_result = await session.execute(strand_query)
                    strands = strand_result.scalars().all()
                    print(f"   ✅ Found {len(strands)} strands for teacher {teacher.id}")
                    if strands:
                        for strand in strands[:2]:
                            print(f"      - {strand.strand_name} ({strand.subject}) - Week {strand.week_number}")
                    
                    # Test Substrand query with teacher ID
                    print("   Testing Substrand query...")
                    substrand_query = select(Substrand).where(Substrand.teacher_id == teacher.id)
                    substrand_result = await session.execute(substrand_query)
                    substrands = substrand_result.scalars().all()
                    print(f"   ✅ Found {len(substrands)} substrands for teacher {teacher.id}")
                    if substrands:
                        for substrand in substrands[:2]:
                            print(f"      - {substrand.substrand_name} (Strand ID: {substrand.strand_id})")
                    
                    # Test ContentStandard query with teacher ID
                    print("   Testing ContentStandard query...")
                    cs_query = select(ContentStandard).where(ContentStandard.teacher_id == teacher.id)
                    cs_result = await session.execute(cs_query)
                    content_standards = cs_result.scalars().all()
                    print(f"   ✅ Found {len(content_standards)} content standards for teacher {teacher.id}")
                    if content_standards:
                        for cs in content_standards[:2]:
                            print(f"      - {cs.content_standard_code or 'No Code'}: {cs.content_standard[:50]}...")
                    
                    # Test Indicator query with teacher ID
                    print("   Testing Indicator query...")
                    indicator_query = select(Indicator).where(Indicator.teacher_id == teacher.id)
                    indicator_result = await session.execute(indicator_query)
                    indicators = indicator_result.scalars().all()
                    print(f"   ✅ Found {len(indicators)} indicators for teacher {teacher.id}")
                    if indicators:
                        for indicator in indicators[:2]:
                            print(f"      - {indicator.indicator_code or 'No Code'}: {indicator.indicator_text[:50]}...")
            
        print("\n=== DEBUGGING COMPLETE ===")
        
    except Exception as e:
        print(f"❌ Debugging failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(debug_teacher_filtering())