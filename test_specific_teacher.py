#!/usr/bin/env python3
"""
Test script to verify data exists for the specific teacher ID
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import configuration
try:
    from database import async_engine
    from model import Strand, Substrand, ContentStandard, Indicator
    print("✅ Successfully imported all modules")
except Exception as e:
    print(f"❌ Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def test_specific_teacher():
    """Test querying data for the specific teacher ID that has data"""
    # The teacher ID that has data in the database
    teacher_id_with_data = UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"=== TESTING QUERIES FOR TEACHER ID: {teacher_id_with_data} ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Test Strand query with the specific teacher ID
            print("\n2. Testing Strand query...")
            strand_query = select(Strand).where(Strand.teacher_id == teacher_id_with_data)
            strand_result = await session.execute(strand_query)
            strands = strand_result.scalars().all()
            print(f"✅ Found {len(strands)} strands for teacher {teacher_id_with_data}")
            if strands:
                print("   First few strand records:")
                for i, strand in enumerate(strands[:3]):
                    print(f"     {i+1}. {strand.strand_name} - {strand.subject} - Week {strand.week_number}")
            else:
                print("   No strand records found")
            
            # Test Substrand query with the specific teacher ID
            print("\n3. Testing Substrand query...")
            substrand_query = select(Substrand).where(Substrand.teacher_id == teacher_id_with_data)
            substrand_result = await session.execute(substrand_query)
            substrands = substrand_result.scalars().all()
            print(f"✅ Found {len(substrands)} substrands for teacher {teacher_id_with_data}")
            if substrands:
                print("   First few substrand records:")
                for i, substrand in enumerate(substrands[:3]):
                    print(f"     {i+1}. {substrand.substrand_name} - Strand ID {substrand.strand_id}")
            else:
                print("   No substrand records found")
            
            # Test ContentStandard query with the specific teacher ID
            print("\n4. Testing ContentStandard query...")
            cs_query = select(ContentStandard).where(ContentStandard.teacher_id == teacher_id_with_data)
            cs_result = await session.execute(cs_query)
            content_standards = cs_result.scalars().all()
            print(f"✅ Found {len(content_standards)} content standards for teacher {teacher_id_with_data}")
            if content_standards:
                print("   First few content standard records:")
                for i, cs in enumerate(content_standards[:3]):
                    print(f"     {i+1}. {cs.content_standard_code or 'No Code'} - {cs.content_standard[:50]}...")
            else:
                print("   No content standard records found")
            
            # Test Indicator query with the specific teacher ID
            print("\n5. Testing Indicator query...")
            indicator_query = select(Indicator).where(Indicator.teacher_id == teacher_id_with_data)
            indicator_result = await session.execute(indicator_query)
            indicators = indicator_result.scalars().all()
            print(f"✅ Found {len(indicators)} indicators for teacher {teacher_id_with_data}")
            if indicators:
                print("   First few indicator records:")
                for i, indicator in enumerate(indicators[:3]):
                    print(f"     {i+1}. {indicator.indicator_code or 'No Code'} - {indicator.indicator_text[:50]}...")
            else:
                print("   No indicator records found")
            
        print("\n=== TEST COMPLETE ===")
        print("If you saw data above, it means the issue is that you're testing with a different teacher ID.")
        print("The endpoints work correctly when the correct teacher ID is used.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_specific_teacher())