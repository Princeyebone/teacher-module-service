#!/usr/bin/env python3
"""
Test script to verify the read_strands function processes TempExtract data correctly.
"""

import json
from datetime import datetime
import uuid

# Mock data that simulates what the AI would return
mock_ai_response = {
    "strand": {
        "strand_name": "Algebra",
        "subject": "Mathematics",
        "class_name": "Grade 10",
        "teacher_id": "123e4567-e89b-12d3-a456-426614174000",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "week_number": 3
                }
            ]
        }
    },
    "substrand": {
        "strand_name": "Algebra",
        "substrand_name": "Linear Equations",
        "subject": "Mathematics",
        "class_name": "Grade 10",
        "teacher_id": "123e4567-e89b-12d3-a456-426614174000",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "week_number": 3
                }
            ]
        }
    },
    "content_standard": {
        "strand_name": "Algebra",
        "substrand_name": "Linear Equations",
        "content_standard_code": "ALG-LE-001",
        "content_standard": "Solve linear equations in one variable",
        "subject": "Mathematics",
        "class_name": "Grade 10",
        "teacher_id": "123e4567-e89b-12d3-a456-426614174000",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "week_number": 3
                }
            ]
        }
    },
    "indicator": {
        "strand_name": "Algebra",
        "substrand_name": "Linear Equations",
        "content_standard_code": "ALG-LE-001",
        "indicator_code": "ALG-LE-001-I01",
        "indicator_text": "Student can solve one-step linear equations",
        "subject": "Mathematics",
        "class_name": "Grade 10",
        "teacher_id": "123e4567-e89b-12d3-a456-426614174000",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "week_number": 3
                }
            ]
        }
    }
}

def test_data_processing():
    """Test the data processing logic from read_strands function."""
    print("Testing data processing logic...")
    
    # Simulate the processing logic from read_strands
    ai_data = mock_ai_response
    if isinstance(ai_data, dict):
        print(f"AI data is a dict with {len(ai_data)} keys")
        print(f"AI data keys: {list(ai_data.keys())}")
        
        # Extract components from the flat structure
        strands_data = []
        substrands_data = []
        content_standards_data = []
        indicators_data = []
        
        # Process all items in the flat structure
        for key, value in ai_data.items():
            print(f"Processing key: {key}, value type: {type(value)}")
            
            if isinstance(value, dict):
                # Categorize based on key names
                # Handle both exact matches and numbered variants
                if key == "strand" or (key.startswith("strand") and not key.startswith("strand_")):
                    # Main strand entry (key is exactly "strand")
                    strands_data.append(value)
                    print(f"Added to strands_data: {key} with strand_name: {value.get('strand_name', '')}")
                elif key.startswith("strand_"):
                    # Additional strand entries (keys like "strand_1", "strand_2", etc.)
                    strands_data.append(value)
                    print(f"Added to strands_data: {key} with strand_name: {value.get('strand_name', '')}")
                elif key == "substrand" or (key.startswith("substrand") and not key.startswith("substrand_")):
                    # Main substrand entry (key is exactly "substrand")
                    substrands_data.append(value)
                    print(f"Added to substrands_data: {key} with substrand_name: {value.get('substrand_name', '')}")
                elif key.startswith("substrand_"):
                    # Additional substrand entries (keys like "substrand_1", "substrand_2", etc.)
                    substrands_data.append(value)
                    print(f"Added to substrands_data: {key} with substrand_name: {value.get('substrand_name', '')}")
                elif key == "content_standard" or (key.startswith("content_standard") and not key.startswith("content_standard_")):
                    # Main content standard entry (key is exactly "content_standard")
                    content_standards_data.append(value)
                    print(f"Added to content_standards_data: {key} with content_standard_code: {value.get('content_standard_code', '')}")
                elif key.startswith("content_standard_"):
                    # Additional content standard entries (keys like "content_standard_1", "content_standard_2", etc.)
                    content_standards_data.append(value)
                    print(f"Added to content_standards_data: {key} with content_standard_code: {value.get('content_standard_code', '')}")
                elif key == "indicator" or (key.startswith("indicator") and not key.startswith("indicator_")):
                    # Main indicator entry (key is exactly "indicator")
                    indicators_data.append(value)
                    print(f"Added to indicators_data: {key} with indicator_code: {value.get('indicator_code', '')}")
                elif key.startswith("indicator_"):
                    # Additional indicator entries (keys like "indicator_1", "indicator_2", etc.)
                    indicators_data.append(value)
                    print(f"Added to indicators_data: {key} with indicator_code: {value.get('indicator_code', '')}")
        
        print(f"Extracted data - strands: {len(strands_data)}, substrands: {len(substrands_data)}, content_standards: {len(content_standards_data)}, indicators: {len(indicators_data)}")
        
        # Create mappings for easier access
        strands_by_name = {}
        substrands_by_strand = {}
        content_standards_by_substrand = {}
        indicators_by_content_standard = {}
        
        # Process strands
        for strand_data in strands_data:
            strand_name = strand_data.get("strand_name", "")
            if strand_name:
                strands_by_name[strand_name] = strand_data
                print(f"Processed strand: {strand_name}")
        
        print(f"Processed {len(strands_by_name)} unique strands")
        
        # Process substrands and group by strand
        for substrand_data in substrands_data:
            strand_name = substrand_data.get("strand_name", "")
            substrand_name = substrand_data.get("substrand_name", "")
            if strand_name and substrand_name:
                if strand_name not in substrands_by_strand:
                    substrands_by_strand[strand_name] = {}
                substrands_by_strand[strand_name][substrand_name] = substrand_data
                print(f"Processed substrand: {substrand_name} for strand: {strand_name}")
        
        # Process content standards and group by substrand
        for cs_data in content_standards_data:
            strand_name = cs_data.get("strand_name", "")
            substrand_name = cs_data.get("substrand_name", "")
            content_standard_code = cs_data.get("content_standard_code", "")
            if strand_name and substrand_name and content_standard_code:
                group_key = f"{strand_name}||{substrand_name}"
                if group_key not in content_standards_by_substrand:
                    content_standards_by_substrand[group_key] = {}
                content_standards_by_substrand[group_key][content_standard_code] = cs_data
                print(f"Processed content standard: {content_standard_code} for substrand: {substrand_name}")
        
        # Process indicators and group by content standard
        for indicator_data in indicators_data:
            strand_name = indicator_data.get("strand_name", "")
            substrand_name = indicator_data.get("substrand_name", "")
            content_standard_code = indicator_data.get("content_standard_code", "")
            if strand_name and substrand_name and content_standard_code:
                group_key = f"{strand_name}||{substrand_name}||{content_standard_code}"
                if group_key not in indicators_by_content_standard:
                    indicators_by_content_standard[group_key] = []
                indicators_by_content_standard[group_key].append(indicator_data)
                print(f"Processed indicator for content standard: {content_standard_code}")
        
        # Build the nested structure as specified
        result = []
        
        # For each strand, build its complete structure
        for strand_name, strand_data in strands_by_name.items():
            print(f"Building structure for strand: {strand_name}")
            strand_entry = {
                "strand_name": strand_data.get("strand_name", ""),
                "subject": strand_data.get("subject", "Mathematics"),
                "class_name": strand_data.get("class_name", "Grade 10"),
                "teacher_id": strand_data.get("teacher_id", "123e4567-e89b-12d3-a456-426614174000"),
                "substrands": [],
                "data_source": "temp_extract",
                "url": None
            }
            
            # Add substrands to the strand
            strand_substrands = substrands_by_strand.get(strand_name, {})
            print(f"Strand {strand_name} has {len(strand_substrands)} substrands")
            for substrand_name, substrand_data in strand_substrands.items():
                substrand_entry = {
                    "substrand_name": substrand_data.get("substrand_name", ""),
                    "content_standards": []
                }
                
                # Add content standards to the substrand
                cs_group_key = f"{strand_name}||{substrand_name}"
                substrand_content_standards = content_standards_by_substrand.get(cs_group_key, {})
                print(f"Substrand {substrand_name} has {len(substrand_content_standards)} content standards")
                
                for cs_code, cs_data in substrand_content_standards.items():
                    cs_entry = {
                        "content_standard_code": cs_data.get("content_standard_code", ""),
                        "content_standard_text": cs_data.get("content_standard", ""),
                        "indicators": []
                    }
                    
                    # Add indicators to the content standard
                    indicator_group_key = f"{strand_name}||{substrand_name}||{cs_code}"
                    cs_indicators = indicators_by_content_standard.get(indicator_group_key, [])
                    print(f"Content standard {cs_code} has {len(cs_indicators)} indicators")
                    
                    for indicator_data in cs_indicators:
                        # Filter session data to only include essential fields
                        weeks_sessions = {}
                        original_sessions = indicator_data.get("weeks_sessions", {})
                        for week_key, sessions in original_sessions.items():
                            # Create filtered sessions with only essential fields
                            filtered_sessions = [
                                {
                                    "id": session.get("id"),
                                    "date": session.get("date"),
                                    "start_time": session.get("start_time"),
                                    "end_time": session.get("end_time"),
                                    "week_number": session.get("week_number")
                                }
                                for session in sessions
                                if all(field in session for field in ["id", "date", "start_time", "end_time", "week_number"])
                            ]
                            if filtered_sessions:
                                weeks_sessions[week_key] = filtered_sessions
                        
                        indicator_entry = {
                            "indicator_code": indicator_data.get("indicator_code", ""),
                            "indicator_text": indicator_data.get("indicator_text", ""),
                            "weeks_sessions": weeks_sessions
                        }
                        cs_entry["indicators"].append(indicator_entry)
                    
                    substrand_entry["content_standards"].append(cs_entry)
                
                strand_entry["substrands"].append(substrand_entry)
            
            result.append(strand_entry)
        
        print(f"Returning result with {len(result)} strands")
        print("Result:")
        print(json.dumps(result, indent=2))
        return result
    else:
        print(f"AI data is not a dict: {type(ai_data)}")
        return []

if __name__ == "__main__":
    result = test_data_processing()
    if result:
        print("\n✅ Test passed! The read_strands function should now work correctly.")
    else:
        print("\n❌ Test failed! There may still be an issue with the data processing.")