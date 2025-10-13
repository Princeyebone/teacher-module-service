#!/usr/bin/env python3
"""
Debug script to identify exactly why read_strands is returning an empty list.
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

async def debug_read_strands_step_by_step(teacher_id, subject, class_name):
    """Debug the read_strands function step by step."""
    print(f"=== DEBUGGING READ_STRANDS STEP BY STEP ===")
    print(f"Parameters:")
    print(f"  Teacher ID: {teacher_id}")
    print(f"  Subject: {subject}")
    print(f"  Class Name: {class_name}")
    print()
    
    try:
        # Create database session
        async with AsyncSession(async_engine) as session:
            print("1. Checking TempExtract for AI-generated semester plan data...")
            
            # Check TempExtract for AI-generated semester plan data
            temp_extract_query = select(TempExtract).where(
                (TempExtract.teacher_id == teacher_id) &
                (TempExtract.subject == subject) &
                (TempExtract.class_name == class_name) &
                (TempExtract.type == "semester plan")
            )
            
            temp_result = await session.execute(temp_extract_query)
            temp_entry = temp_result.scalar_one_or_none()
            
            print(f"   TempExtract query result: {temp_entry is not None}")
            
            if temp_entry:
                print("2. TempExtract entry found!")
                print(f"   ID: {temp_entry.id}")
                print(f"   Type: {temp_entry.type}")
                print(f"   Subject: {temp_entry.subject}")
                print(f"   Class Name: {temp_entry.class_name}")
                print(f"   Created At: {temp_entry.created_at}")
                print(f"   Updated At: {temp_entry.updated_at}")
                print(f"   File URL: {temp_entry.file}")
                print(f"   Data is present: {temp_entry.data is not None}")
                
                if temp_entry.data:
                    print(f"   Data type: {type(temp_entry.data)}")
                    if isinstance(temp_entry.data, dict):
                        print(f"   Data keys: {list(temp_entry.data.keys())}")
                    elif isinstance(temp_entry.data, list):
                        print(f"   Data length: {len(temp_entry.data)}")
                    else:
                        print(f"   Data content: {temp_entry.data}")
                    
                    print("3. Processing TempExtract data...")
                    
                    # Simulate the exact logic from read_strands function
                    ai_data = temp_entry.data
                    
                    if isinstance(ai_data, list):
                        print("   Detected new format: array of strands")
                        print(f"   Number of strands: {len(ai_data)}")
                        
                        result = []
                        for i, strand_data in enumerate(ai_data):
                            print(f"   Processing strand {i+1}:")
                            print(f"     Strand name: {strand_data.get('strand_name', 'N/A')}")
                            print(f"     Number of substrands: {len(strand_data.get('substrands', []))}")
                            
                            strand_entry = {
                                "strand_name": strand_data.get("strand_name", ""),
                                "subject": strand_data.get("subject", subject),
                                "class_name": strand_data.get("class_name", class_name),
                                "teacher_id": strand_data.get("teacher_id", str(teacher_id)),
                                "substrands": strand_data.get("substrands", []),
                                "data_source": "temp_extract",
                                "url": temp_entry.file if hasattr(temp_entry, 'file') else None
                            }
                            result.append(strand_entry)
                        
                        print(f"   Final result: {len(result)} strands")
                        print("   Result preview:")
                        print(json.dumps(result, indent=2, default=str)[:500] + "..." if len(json.dumps(result, default=str)) > 500 else json.dumps(result, indent=2, default=str))
                        return result
                        
                    elif isinstance(ai_data, dict):
                        print("   Detected old format: flat structure")
                        print(f"   Number of keys: {len(ai_data)}")
                        
                        # Extract components from the flat structure
                        strands_data = []
                        substrands_data = []
                        content_standards_data = []
                        indicators_data = []
                        
                        # Process all items in the flat structure
                        for key, value in ai_data.items():
                            print(f"   Processing key: {key}")
                            if isinstance(value, dict):
                                if key == "strand" or (key.startswith("strand") and not key.startswith("strand_")):
                                    strands_data.append(value)
                                    print(f"     -> Added to strands_data")
                                elif key.startswith("strand_"):
                                    strands_data.append(value)
                                    print(f"     -> Added to strands_data")
                                elif key == "substrand" or (key.startswith("substrand") and not key.startswith("substrand_")):
                                    substrands_data.append(value)
                                    print(f"     -> Added to substrands_data")
                                elif key.startswith("substrand_"):
                                    substrands_data.append(value)
                                    print(f"     -> Added to substrands_data")
                                elif key == "content_standard" or (key.startswith("content_standard") and not key.startswith("content_standard_")):
                                    content_standards_data.append(value)
                                    print(f"     -> Added to content_standards_data")
                                elif key.startswith("content_standard_"):
                                    content_standards_data.append(value)
                                    print(f"     -> Added to content_standards_data")
                                elif key == "indicator" or (key.startswith("indicator") and not key.startswith("indicator_")):
                                    indicators_data.append(value)
                                    print(f"     -> Added to indicators_data")
                                elif key.startswith("indicator_"):
                                    indicators_data.append(value)
                                    print(f"     -> Added to indicators_data")
                        
                        print(f"   Extracted data - strands: {len(strands_data)}, substrands: {len(substrands_data)}, content_standards: {len(content_standards_data)}, indicators: {len(indicators_data)}")
                        
                        if not strands_data:
                            print("   ❌ No strand data found - this will result in an empty list")
                            return []
                        
                        # Build the nested structure as specified
                        result = []
                        for strand_data in strands_data:
                            strand_entry = {
                                "strand_name": strand_data.get("strand_name", ""),
                                "subject": strand_data.get("subject", subject),
                                "class_name": strand_data.get("class_name", class_name),
                                "teacher_id": strand_data.get("teacher_id", str(teacher_id)),
                                "substrands": [],  # In the old format, we'd build this, but for debugging we'll leave it empty
                                "data_source": "temp_extract",
                                "url": temp_entry.file if hasattr(temp_entry, 'file') else None
                            }
                            result.append(strand_entry)
                        
                        print(f"   Final result: {len(result)} strands")
                        return result
                    else:
                        print(f"   ❌ Unexpected data type: {type(ai_data)}")
                        return []
                else:
                    print("   ❌ Data is None or empty")
                    return []
            else:
                print("2. ❌ No TempExtract entry found for the given parameters.")
                
                # Check if there are any TempExtract entries for this teacher at all
                print("3. Checking for any TempExtract entries for this teacher...")
                all_entries_query = select(TempExtract).where(
                    (TempExtract.teacher_id == teacher_id) &
                    (TempExtract.type == "semester plan")
                )
                
                all_result = await session.execute(all_entries_query)
                all_entries = all_result.scalars().all()
                
                if all_entries:
                    print(f"   Found {len(all_entries)} other TempExtract entries for this teacher:")
                    for entry in all_entries:
                        print(f"     - Subject: {entry.subject}, Class: {entry.class_name}, Updated: {entry.updated_at}")
                else:
                    print("   No TempExtract entries found for this teacher at all.")
                
                return []
                    
    except Exception as e:
        print(f"💥 Error during debugging: {e}")
        import traceback
        traceback.print_exc()
        return []

# Example usage - modify these values to match your actual data
if __name__ == "__main__":
    import asyncio
    
    # Replace these with your actual values
    teacher_id = "your-teacher-id-here"  # Replace with actual teacher ID
    subject = "your-subject-here"  # Replace with actual subject
    class_name = "your-class-name-here"  # Replace with actual class name
    
    # Check if the values have been updated
    if teacher_id == "your-teacher-id-here":
        print("Please update the teacher_id, subject, and class_name variables in this script")
        print("with your actual values before running.")
        print()
        print("Example:")
        print('teacher_id = "123e4567-e89b-12d3-a456-426614174000"')
        print('subject = "Mathematics"')
        print('class_name = "Grade 10"')
    else:
        result = asyncio.run(debug_read_strands_step_by_step(teacher_id, subject, class_name))
        print(f"\n=== FINAL RESULT ===")
        if result:
            print(f"✅ Success! Returned {len(result)} items:")
            print(json.dumps(result, indent=2, default=str))
        else:
            print("❌ Failed! Returned empty list.")