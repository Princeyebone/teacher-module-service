#!/usr/bin/env python3
"""
Examine the actual data structure in the database
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

async def examine_data_structure():
    """Examine the actual data structure in the database"""
    # The teacher ID that has data in the database
    teacher_id_with_data = UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"=== EXAMINING DATA STRUCTURE FOR TEACHER ID: {teacher_id_with_data} ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Examine Strand data structure
            print("\n2. Examining Strand data structure...")
            strand_query = select(Strand).where(Strand.teacher_id == teacher_id_with_data)
            strand_result = await session.execute(strand_query)
            strands = strand_result.scalars().all()
            print(f"✅ Found {len(strands)} strands")
            if strands:
                strand = strands[0]
                print(f"   Strand structure:")
                print(f"     id: {strand.id}")
                print(f"     strand_name: {strand.strand_name}")
                print(f"     subject: {strand.subject}")
                print(f"     class_name: {strand.class_name}")
                print(f"     teacher_id: {strand.teacher_id}")
                print(f"     week_number: {strand.week_number}")
                print(f"     session_ids: {strand.session_ids}")
                print(f"     session_details: {strand.session_details[:1] if strand.session_details else []}...")  # First item only
                print(f"     created_at: {strand.created_at}")
                print(f"     updated_at: {strand.updated_at}")
            
            # Examine Substrand data structure
            print("\n3. Examining Substrand data structure...")
            substrand_query = select(Substrand).where(Substrand.teacher_id == teacher_id_with_data)
            substrand_result = await session.execute(substrand_query)
            substrands = substrand_result.scalars().all()
            print(f"✅ Found {len(substrands)} substrands")
            if substrands:
                substrand = substrands[0]
                print(f"   Substrand structure:")
                print(f"     id: {substrand.id}")
                print(f"     substrand_name: {substrand.substrand_name}")
                print(f"     strand_id: {substrand.strand_id}")
                print(f"     subject: {substrand.subject}")
                print(f"     class_name: {substrand.class_name}")
                print(f"     teacher_id: {substrand.teacher_id}")
                print(f"     week_numbers: {substrand.week_numbers}")
                print(f"     session_ids: {substrand.session_ids}")
                print(f"     session_details: {substrand.session_details[:1] if substrand.session_details else []}...")  # First item only
                print(f"     created_at: {substrand.created_at}")
                print(f"     updated_at: {substrand.updated_at}")
            
            # Examine ContentStandard data structure
            print("\n4. Examining ContentStandard data structure...")
            cs_query = select(ContentStandard).where(ContentStandard.teacher_id == teacher_id_with_data)
            cs_result = await session.execute(cs_query)
            content_standards = cs_result.scalars().all()
            print(f"✅ Found {len(content_standards)} content standards")
            if content_standards:
                cs = content_standards[0]
                print(f"   ContentStandard structure:")
                print(f"     id: {cs.id}")
                print(f"     content_standard_code: {cs.content_standard_code}")
                print(f"     content_standard: {cs.content_standard}")
                print(f"     substrand_id: {cs.substrand_id}")
                print(f"     subject: {cs.subject}")
                print(f"     class_name: {cs.class_name}")
                print(f"     teacher_id: {cs.teacher_id}")
                print(f"     session_ids: {cs.session_ids}")
                print(f"     session_details: {cs.session_details[:1] if cs.session_details else []}...")  # First item only
                print(f"     created_at: {cs.created_at}")
                print(f"     updated_at: {cs.updated_at}")
            
            # Examine Indicator data structure
            print("\n5. Examining Indicator data structure...")
            indicator_query = select(Indicator).where(Indicator.teacher_id == teacher_id_with_data)
            indicator_result = await session.execute(indicator_query)
            indicators = indicator_result.scalars().all()
            print(f"✅ Found {len(indicators)} indicators")
            if indicators:
                indicator = indicators[0]
                print(f"   Indicator structure:")
                print(f"     id: {indicator.id}")
                print(f"     indicator_code: {indicator.indicator_code}")
                print(f"     indicator_text: {indicator.indicator_text}")
                print(f"     content_standard_id: {indicator.content_standard_id}")
                print(f"     subject: {indicator.subject}")
                print(f"     class_name: {indicator.class_name}")
                print(f"     teacher_id: {indicator.teacher_id}")
                print(f"     session_ids: {indicator.session_ids}")
                print(f"     session_details: {indicator.session_details[:1] if indicator.session_details else []}...")  # First item only
                print(f"     created_at: {indicator.created_at}")
                print(f"     updated_at: {indicator.updated_at}")
            
        print("\n=== EXAMINATION COMPLETE ===")
        
    except Exception as e:
        print(f"❌ Examination failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(examine_data_structure())