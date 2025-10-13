#!/usr/bin/env python3
"""
Test script to verify the rewritten endpoints work correctly
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
    from model import Strand, Substrand, ContentStandard, Indicator, TeacherProfile
    from schemas import SessionDetail
    print("✅ Successfully imported all modules")
except Exception as e:
    print(f"❌ Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def test_rewritten_endpoints():
    """Test the rewritten endpoints logic"""
    # The teacher ID that has data in the database
    teacher_id_with_data = UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"=== TESTING REWRITTEN ENDPOINTS LOGIC FOR TEACHER ID: {teacher_id_with_data} ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Test the read-strands logic (rewritten)
            print("\n2. Testing read-strands logic...")
            strand_query = select(Strand).where(Strand.teacher_id == teacher_id_with_data)
            strand_result = await session.execute(strand_query)
            strands = strand_result.scalars().all()
            print(f"✅ Found {len(strands)} strands")
            
            # Simulate the new grouping logic
            strand_groups = {}
            for strand in strands:
                key = (strand.strand_name, strand.subject, strand.class_name)
                if key not in strand_groups:
                    strand_groups[key] = {
                        "id": strand.id,
                        "strand_name": strand.strand_name,
                        "subject": strand.subject,
                        "class_name": strand.class_name,
                        "teacher_id": strand.teacher_id,
                        "weeks_sessions": {},
                        "substrands": [],
                        "created_at": strand.created_at,
                        "updated_at": strand.updated_at,
                        "data_source": "strand_table"
                    }
                # Add week data
                week_key = f"Week {strand.week_number}"
                strand_groups[key]["weeks_sessions"][week_key] = [
                    SessionDetail(**detail) for detail in strand.session_details
                ]
            
            print(f"   Grouped into {len(strand_groups)} strand groups")
            for key, group in strand_groups.items():
                print(f"     - {group['strand_name']} ({group['subject']}): {len(group['weeks_sessions'])} weeks")
            
            # Test hierarchical data fetching for one strand group
            if strand_groups:
                key, strand_data = next(iter(strand_groups.items()))
                print(f"\n3. Testing hierarchical data fetching for {strand_data['strand_name']}...")
                
                # Fetch substrands for this strand
                substrand_query = select(Substrand).where(
                    Substrand.strand_id == strand_data["id"]
                )
                substrand_result = await session.execute(substrand_query)
                substrands = substrand_result.scalars().all()
                print(f"   Found {len(substrands)} substrands")
                
                # Test content standards fetching
                if substrands:
                    substrand = substrands[0]
                    print(f"   Testing content standards for {substrand.substrand_name}...")
                    cs_query = select(ContentStandard).where(
                        ContentStandard.substrand_id == substrand.id
                    )
                    cs_result = await session.execute(cs_query)
                    content_standards = cs_result.scalars().all()
                    print(f"   Found {len(content_standards)} content standards")
                    
                    # Test indicators fetching
                    if content_standards:
                        cs = content_standards[0]
                        print(f"   Testing indicators for {cs.content_standard_code}...")
                        indicator_query = select(Indicator).where(
                            Indicator.content_standard_id == cs.id
                        )
                        indicator_result = await session.execute(indicator_query)
                        indicators = indicator_result.scalars().all()
                        print(f"   Found {len(indicators)} indicators")
            
            # Test the read-substrands logic (rewritten)
            print("\n4. Testing read-substrands logic...")
            substrand_query = select(Substrand).where(Substrand.teacher_id == teacher_id_with_data)
            substrand_result = await session.execute(substrand_query)
            substrands = substrand_result.scalars().all()
            print(f"✅ Found {len(substrands)} substrands")
            
            # Test building response with strand names
            response = []
            for substrand in substrands[:3]:  # Test with first 3
                strand_query = select(Strand).where(Strand.id == substrand.strand_id)
                strand_result = await session.execute(strand_query)
                strand = strand_result.scalar_one_or_none()
                
                if strand:
                    print(f"     - {substrand.substrand_name} -> {strand.strand_name}")
            
            # Test the read-content-standards logic (rewritten)
            print("\n5. Testing read-content-standards logic...")
            cs_query = select(ContentStandard).where(ContentStandard.teacher_id == teacher_id_with_data)
            cs_result = await session.execute(cs_query)
            content_standards = cs_result.scalars().all()
            print(f"✅ Found {len(content_standards)} content standards")
            
            # Test building response with hierarchy
            for cs in content_standards[:3]:  # Test with first 3
                substrand_query = select(Substrand).where(Substrand.id == cs.substrand_id)
                substrand_result = await session.execute(substrand_query)
                substrand = substrand_result.scalar_one_or_none()
                
                if substrand:
                    strand_query = select(Strand).where(Strand.id == substrand.strand_id)
                    strand_result = await session.execute(strand_query)
                    strand = strand_result.scalar_one_or_none()
                    
                    print(f"     - {cs.content_standard_code} -> {substrand.substrand_name} -> {strand.strand_name if strand else 'Unknown'}")
            
            # Test the read-indicators logic (rewritten)
            print("\n6. Testing read-indicators logic...")
            indicator_query = select(Indicator).where(Indicator.teacher_id == teacher_id_with_data)
            indicator_result = await session.execute(indicator_query)
            indicators = indicator_result.scalars().all()
            print(f"✅ Found {len(indicators)} indicators")
            
            # Test building response with full hierarchy
            for indicator in indicators[:3]:  # Test with first 3
                cs_query = select(ContentStandard).where(ContentStandard.id == indicator.content_standard_id)
                cs_result = await session.execute(cs_query)
                content_standard = cs_result.scalar_one_or_none()
                
                if content_standard:
                    substrand_query = select(Substrand).where(Substrand.id == content_standard.substrand_id)
                    substrand_result = await session.execute(substrand_query)
                    substrand = substrand_result.scalar_one_or_none()
                    
                    if substrand:
                        strand_query = select(Strand).where(Strand.id == substrand.strand_id)
                        strand_result = await session.execute(strand_query)
                        strand = strand_result.scalar_one_or_none()
                        
                        print(f"     - {indicator.indicator_code} -> {content_standard.content_standard_code} -> {substrand.substrand_name} -> {strand.strand_name if strand else 'Unknown'}")
            
        print("\n=== TEST COMPLETE ===")
        print("The rewritten endpoints logic should now work correctly and return hierarchical data.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_rewritten_endpoints())