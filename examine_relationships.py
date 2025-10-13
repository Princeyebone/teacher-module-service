#!/usr/bin/env python3
"""
Examine the relationships between tables
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

async def examine_relationships():
    """Examine the relationships between tables"""
    # The teacher ID that has data in the database
    teacher_id_with_data = UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"=== EXAMINING RELATIONSHIPS FOR TEACHER ID: {teacher_id_with_data} ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Get a strand to start with
            print("\n2. Getting a strand...")
            strand_query = select(Strand).where(Strand.teacher_id == teacher_id_with_data)
            strand_result = await session.execute(strand_query)
            strands = strand_result.scalars().all()
            if strands:
                strand = strands[0]
                print(f"   Found strand: {strand.strand_name} (ID: {strand.id})")
                
                # Get substrands for this strand
                print("\n3. Getting substrands for this strand...")
                substrand_query = select(Substrand).where(Substrand.strand_id == strand.id)
                substrand_result = await session.execute(substrand_query)
                substrands = substrand_result.scalars().all()
                print(f"   Found {len(substrands)} substrands for strand {strand.strand_name}")
                for substrand in substrands:
                    print(f"     - {substrand.substrand_name} (ID: {substrand.id})")
                    
                    # Get content standards for this substrand
                    print(f"\n4. Getting content standards for substrand {substrand.substrand_name}...")
                    cs_query = select(ContentStandard).where(ContentStandard.substrand_id == substrand.id)
                    cs_result = await session.execute(cs_query)
                    content_standards = cs_result.scalars().all()
                    print(f"   Found {len(content_standards)} content standards for substrand {substrand.substrand_name}")
                    for cs in content_standards:
                        print(f"     - {cs.content_standard_code or 'No Code'}: {cs.content_standard[:50]}...")
                        
                        # Get indicators for this content standard
                        print(f"\n5. Getting indicators for content standard {cs.content_standard_code}...")
                        indicator_query = select(Indicator).where(Indicator.content_standard_id == cs.id)
                        indicator_result = await session.execute(indicator_query)
                        indicators = indicator_result.scalars().all()
                        print(f"   Found {len(indicators)} indicators for content standard {cs.content_standard_code}")
                        for indicator in indicators[:3]:  # Show first 3
                            print(f"     - {indicator.indicator_code or 'No Code'}: {indicator.indicator_text[:50]}...")
            
        print("\n=== RELATIONSHIP EXAMINATION COMPLETE ===")
        
    except Exception as e:
        print(f"❌ Examination failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(examine_relationships())