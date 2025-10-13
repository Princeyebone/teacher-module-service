"""Debug script to examine tempextract data structure"""

import json
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from model import TempExtract
from config import settings
from uuid import UUID

# Use the same async engine as in the main application
async_engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def debug_tempextract_data():
    """Debug function to examine tempextract data"""
    print("Debugging tempextract data...")
    
    # Create database session
    async with AsyncSession(async_engine) as session:
        try:
            # Get all semester plan entries
            result = await session.execute(
                select(TempExtract).where(TempExtract.type == "semester plan")
            )
            entries = result.scalars().all()
            
            print(f"Found {len(entries)} semester plan entries in tempextract")
            
            for i, entry in enumerate(entries):
                print(f"\n--- Entry {i+1} ---")
                print(f"ID: {entry.id}")
                print(f"Teacher ID: {entry.teacher_id}")
                print(f"Class Name: {entry.class_name}")
                print(f"Subject: {entry.subject}")
                print(f"Type: {entry.type}")
                print(f"Created: {entry.created_at}")
                print(f"Updated: {entry.updated_at}")
                print(f"File: {entry.file}")
                
                # Examine the data structure
                if entry.data:
                    print(f"Data keys: {list(entry.data.keys()) if isinstance(entry.data, dict) else 'Not a dict'}")
                    print(f"Data type: {type(entry.data)}")
                    
                    # Check for components with pattern matching
                    if isinstance(entry.data, dict):
                        strand_keys = [k for k in entry.data.keys() if k.startswith('strand_') or k == 'strand']
                        substrand_keys = [k for k in entry.data.keys() if k.startswith('substrand_') or k == 'substrand']
                        content_standard_keys = [k for k in entry.data.keys() if k.startswith('content_standard_') or k == 'content_standard']
                        indicator_keys = [k for k in entry.data.keys() if k.startswith('indicator_') or k == 'indicator']
                        
                        print(f"Strand keys: {strand_keys}")
                        print(f"Substrand keys: {substrand_keys}")
                        print(f"Content standard keys: {content_standard_keys}")
                        print(f"Indicator keys: {indicator_keys}")
                        
                        # Show first few of each type
                        for key_type, keys in [("strand", strand_keys), ("substrand", substrand_keys), 
                                              ("content_standard", content_standard_keys), ("indicator", indicator_keys)]:
                            if keys:
                                print(f"\nFirst {key_type} entry ({keys[0]}):")
                                first_entry = entry.data[keys[0]]
                                if isinstance(first_entry, dict):
                                    print(f"  Keys: {list(first_entry.keys())}")
                                    # Show a few key values
                                    for k in list(first_entry.keys())[:5]:
                                        print(f"  {k}: {first_entry[k]}")
                        
                        # Check if it has the structured_output format
                        if "structured_output" in entry.data:
                            print("Found structured_output format")
                            print(f"Structured output keys: {list(entry.data['structured_output'].keys())}")
                    else:
                        print(f"Data content: {str(entry.data)[:200]}...")
                else:
                    print("No data found")
                    
        except Exception as e:
            print(f"Error querying tempextract: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("Running tempextract data debug...")
    asyncio.run(debug_tempextract_data())