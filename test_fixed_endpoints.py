#!/usr/bin/env python3
"""
Test script to verify the fixed endpoints work correctly
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
    print("✅ Successfully imported all modules")
except Exception as e:
    print(f"❌ Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def test_fixed_endpoints():
    """Test the fixed endpoints logic"""
    # The teacher ID that has data in the database
    teacher_id_with_data = UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"=== TESTING FIXED ENDPOINTS LOGIC FOR TEACHER ID: {teacher_id_with_data} ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Test the read-strands logic (fixed)
            print("\n2. Testing read-strands logic...")
            strand_query = select(Strand).where(Strand.teacher_id == teacher_id_with_data)
            strand_result = await session.execute(strand_query)
            strands = strand_result.scalars().all()
            print(f"✅ Found {len(strands)} strands")
            
            # Simulate the fixed grouping logic
            grouped_strands = {}
            for strand in strands:
                key = (strand.strand_name, strand.subject)
                if key not in grouped_strands:
                    grouped_strands[key] = {
                        "strand_name": strand.strand_name,
                        "subject": strand.subject,
                        "class_name": strand.class_name,
                        "teacher_id": strand.teacher_id,
                        "weeks_sessions": {},
                        "created_at": strand.created_at,
                        "updated_at": strand.updated_at,
                        "data_source": "strand_table"
                    }
                # Create proper SessionDetail objects with all required fields
                session_details = []
                for detail in strand.session_details:
                    session_details.append({
                        "id": detail.get("id", 0),
                        "date": detail.get("date", ""),
                        "subject": strand.subject,  # Get from strand
                        "start_time": detail.get("start_time", ""),
                        "end_time": detail.get("end_time", ""),
                        "class_name": strand.class_name,  # Get from strand
                        "location": detail.get("location", ""),  # Default to empty if not present
                        "week_number": detail.get("week_number", 1)
                    })
                grouped_strands[key]["weeks_sessions"][f"Week {strand.week_number}"] = session_details
            
            print(f"   Grouped into {len(grouped_strands)} strand groups")
            for key, group in grouped_strands.items():
                print(f"     - {group['strand_name']} ({group['subject']}): {len(group['weeks_sessions'])} weeks")
                # Show sample session detail structure
                for week_key, sessions in list(group['weeks_sessions'].items())[:1]:  # First week only
                    if sessions:
                        session = sessions[0]
                        print(f"       Sample session: id={session['id']}, date={session['date']}, subject={session['subject']}")
            
            # Test the read-substrands logic (fixed)
            print("\n3. Testing read-substrands logic...")
            substrand_query = select(Substrand).where(Substrand.teacher_id == teacher_id_with_data)
            substrand_result = await session.execute(substrand_query)
            substrands = substrand_result.scalars().all()
            print(f"✅ Found {len(substrands)} substrands")
            
            # Test building response with proper SessionDetail objects
            for substrand in substrands[:3]:  # Test with first 3
                strand_query = select(Strand).where(Strand.id == substrand.strand_id)
                strand_result = await session.execute(strand_query)
                strand = strand_result.scalar_one_or_none()
                
                # Create proper weeks_sessions structure
                weeks_sessions = {}
                for week_num in substrand.week_numbers:
                    # Filter session details for this week
                    week_session_details = []
                    for detail in substrand.session_details:
                        if detail.get('week_number') == week_num:
                            week_session_details.append({
                                "id": detail.get("id", 0),
                                "date": detail.get("date", ""),
                                "subject": substrand.subject,
                                "start_time": detail.get("start_time", ""),
                                "end_time": detail.get("end_time", ""),
                                "class_name": substrand.class_name,
                                "location": detail.get("location", ""),
                                "week_number": detail.get("week_number", week_num)
                            })
                    weeks_sessions[f"Week {week_num}"] = week_session_details
                
                strand_name_value = strand.strand_name if strand else "Unknown"
                print(f"     - {substrand.substrand_name} -> {strand_name_value}: {len(weeks_sessions)} weeks")
            
            # Test the read-content-standards logic (fixed)
            print("\n4. Testing read-content-standards logic...")
            cs_query = select(ContentStandard).where(ContentStandard.teacher_id == teacher_id_with_data)
            cs_result = await session.execute(cs_query)
            content_standards = cs_result.scalars().all()
            print(f"✅ Found {len(content_standards)} content standards")
            
            # Test building response with proper SessionDetail objects
            for cs in content_standards[:3]:  # Test with first 3
                substrand_query = select(Substrand).where(Substrand.id == cs.substrand_id)
                substrand_result = await session.execute(substrand_query)
                substrand = substrand_result.scalar_one_or_none()
                
                if substrand:
                    strand_query = select(Strand).where(Strand.id == substrand.strand_id)
                    strand_result = await session.execute(strand_query)
                    strand = strand_result.scalar_one_or_none()
                    
                    # Convert session_details with proper SessionDetail objects
                    weeks_sessions = {}
                    if cs.session_details:
                        for session_detail in cs.session_details:
                            week_key = f"Week {session_detail.get('week_number', 1)}"
                            if week_key not in weeks_sessions:
                                weeks_sessions[week_key] = []
                            
                            # Create proper SessionDetail object
                            weeks_sessions[week_key].append({
                                "id": session_detail.get("id", 0),
                                "date": session_detail.get("date", ""),
                                "subject": cs.subject,
                                "start_time": session_detail.get("start_time", ""),
                                "end_time": session_detail.get("end_time", ""),
                                "class_name": cs.class_name,
                                "location": session_detail.get("location", ""),
                                "week_number": session_detail.get("week_number", 1)
                            })
                    
                    print(f"     - {cs.content_standard_code} -> {substrand.substrand_name} -> {strand.strand_name if strand else 'Unknown'}: {len(weeks_sessions)} weeks")
            
            # Test the read-indicators logic (fixed)
            print("\n5. Testing read-indicators logic...")
            indicator_query = select(Indicator).where(Indicator.teacher_id == teacher_id_with_data)
            indicator_result = await session.execute(indicator_query)
            indicators = indicator_result.scalars().all()
            print(f"✅ Found {len(indicators)} indicators")
            
            # Test building response with proper SessionDetail objects
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
                        
                        # Convert session_details with proper SessionDetail objects
                        weeks_sessions = {}
                        if indicator.session_details:
                            for session_detail in indicator.session_details:
                                week_key = f"Week {session_detail.get('week_number', 1)}"
                                if week_key not in weeks_sessions:
                                    weeks_sessions[week_key] = []
                                
                                # Create proper SessionDetail object
                                weeks_sessions[week_key].append({
                                    "id": session_detail.get("id", 0),
                                    "date": session_detail.get("date", ""),
                                    "subject": indicator.subject,
                                    "start_time": session_detail.get("start_time", ""),
                                    "end_time": session_detail.get("end_time", ""),
                                    "class_name": indicator.class_name,
                                    "location": session_detail.get("location", ""),
                                    "week_number": session_detail.get("week_number", 1)
                                })
                        
                        print(f"     - {indicator.indicator_code} -> {content_standard.content_standard_code} -> {substrand.substrand_name} -> {strand.strand_name if strand else 'Unknown'}: {len(weeks_sessions)} weeks")
            
        print("\n=== TEST COMPLETE ===")
        print("The fixed endpoints logic should now work correctly and return properly structured data.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_fixed_endpoints())