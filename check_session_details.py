#!/usr/bin/env python3
"""
Check what fields are actually in the session details
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
    from model import Strand
    print("✅ Successfully imported all modules")
except Exception as e:
    print(f"❌ Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

async def check_session_details():
    """Check what fields are actually in the session details"""
    # The teacher ID that has data in the database
    teacher_id_with_data = UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"=== CHECKING SESSION DETAILS FOR TEACHER ID: {teacher_id_with_data} ===")
    
    try:
        # Create a session
        print("1. Creating database session...")
        async with AsyncSession(async_engine) as session:
            print("✅ Session created successfully")
            
            # Get a strand to examine its session details
            print("\n2. Getting a strand...")
            strand_query = select(Strand).where(Strand.teacher_id == teacher_id_with_data)
            strand_result = await session.execute(strand_query)
            strands = strand_result.scalars().all()
            if strands:
                strand = strands[0]
                print(f"   Found strand: {strand.strand_name} (ID: {strand.id})")
                print(f"   Session details structure:")
                if strand.session_details:
                    session_detail = strand.session_details[0] if strand.session_details else {}
                    print(f"     Fields in session detail: {list(session_detail.keys())}")
                    print(f"     Sample data: {session_detail}")
                else:
                    print("     No session details found")
            
        print("\n=== SESSION DETAILS CHECK COMPLETE ===")
        
    except Exception as e:
        print(f"❌ Check failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(check_session_details())