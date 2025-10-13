#!/usr/bin/env python3
"""
Debug script to identify why read_strands is returning an empty list.
"""

import json
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import necessary modules
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from model import TempExtract

# Create async engine
async_engine = create_async_engine(settings.DATABASE_URL)

async def debug_temp_extract(teacher_id, subject, class_name):
    """Debug TempExtract data for the given parameters."""
    print(f"Debugging TempExtract for:")
    print(f"  Teacher ID: {teacher_id}")
    print(f"  Subject: {subject}")
    print(f"  Class Name: {class_name}")
    print()
    
    try:
        # Create database session
        async with AsyncSession(async_engine) as session:
            # Check TempExtract for AI-generated semester plan data
            temp_extract_query = select(TempExtract).where(
                (TempExtract.teacher_id == teacher_id) &
                (TempExtract.subject == subject) &
                (TempExtract.class_name == class_name) &
                (TempExtract.type == "semester plan")
            )
            
            temp_result = await session.execute(temp_extract_query)
            temp_entry = temp_result.scalar_one_or_none()
            
            if temp_entry:
                print("✅ TempExtract entry found!")
                print(f"  ID: {temp_entry.id}")
                print(f"  Type: {temp_entry.type}")
                print(f"  Subject: {temp_entry.subject}")
                print(f"  Class Name: {temp_entry.class_name}")
                print(f"  Created At: {temp_entry.created_at}")
                print(f"  Updated At: {temp_entry.updated_at}")
                print(f"  File URL: {temp_entry.file}")
                print(f"  Data is present: {temp_entry.data is not None}")
                
                if temp_entry.data:
                    print(f"  Data type: {type(temp_entry.data)}")
                    print(f"  Data keys: {list(temp_entry.data.keys()) if isinstance(temp_entry.data, dict) else 'Not a dict'}")
                    print("  Data content:")
                    print(json.dumps(temp_entry.data, indent=2, default=str))
                    
                    # Test the processing logic
                    print("\n" + "="*50)
                    print("TESTING PROCESSING LOGIC:")
                    print("="*50)
                    
                    # Import the debug function
                    from debug_read_strands_function import debug_read_strands_logic
                    result = debug_read_strands_logic(temp_entry.data, subject, class_name, teacher_id)
                    print(f"\nFinal result has {len(result)} items")
                    if result:
                        print("✅ Processing successful!")
                    else:
                        print("❌ Processing failed - returned empty list")
                else:
                    print("  ❌ Data is None or empty")
            else:
                print("❌ No TempExtract entry found for the given parameters.")
                print("  This could be why read_strands is returning an empty list.")
                
                # Let's check if there are any TempExtract entries for this teacher
                all_entries_query = select(TempExtract).where(
                    (TempExtract.teacher_id == teacher_id) &
                    (TempExtract.type == "semester plan")
                )
                
                all_result = await session.execute(all_entries_query)
                all_entries = all_result.scalars().all()
                
                if all_entries:
                    print(f"\n📝 Found {len(all_entries)} other TempExtract entries for this teacher:")
                    for entry in all_entries:
                        print(f"  - Subject: {entry.subject}, Class: {entry.class_name}")
                else:
                    print("\n📝 No TempExtract entries found for this teacher at all.")
                    
    except Exception as e:
        print(f"💥 Error during debugging: {e}")
        import traceback
        traceback.print_exc()

# Example usage - modify these values to match your actual data
if __name__ == "__main__":
    import asyncio
    
    # Replace these with your actual values
    teacher_id = "your-teacher-id-here"  # Replace with actual teacher ID
    subject = "Mathematics"  # Replace with actual subject
    class_name = "Grade 10"  # Replace with actual class name
    
    # Check if the values have been updated
    if teacher_id == "your-teacher-id-here":
        print("Please update the teacher_id, subject, and class_name variables in this script")
        print("with your actual values before running.")
    else:
        asyncio.run(debug_temp_extract(teacher_id, subject, class_name))