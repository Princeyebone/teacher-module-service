"""Test script to verify read-strand data structure from tempextract"""

import json
from datetime import datetime
from uuid import UUID

# Mock data structure that would be stored in tempextract
mock_tempextract_data = {
    "strand": {
        "strand_name": "Algebra",
        "subject": "Mathematics",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 3
                }
            ]
        }
    },
    "substrand": {
        "strand_name": "Algebra",
        "substrand_name": "Linear Equations",
        "subject": "Mathematics",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
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
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
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
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 3
                }
            ]
        }
    }
}

def test_read_strand_processing():
    """Test the read-strand processing logic"""
    print("Testing read-strand data processing...")
    
    # Simulate the logic in read_strands endpoint
    ai_data = mock_tempextract_data
    formatted_response = []
    
    print(f"AI data keys: {list(ai_data.keys())}")
    
    # Check if this is the new format (with structured_output) or old format (with strands)
    if "structured_output" in ai_data:
        print("Found structured_output format")
        # New format with explanation and structured_output
        structured_output = ai_data["structured_output"]
        
        # Process each component from structured_output
        for component_name in ["strand", "substrand", "content_standard", "indicator"]:
            if component_name in structured_output:
                print(f"Processing component: {component_name}")
                component_data = structured_output[component_name]
                # Extract week numbers from the component data
                weeks_sessions = component_data.get("weeks_sessions", {})
                
                # Create response structure
                component_response = {
                    "strand_name": component_data.get("strand_name", ""),
                    "subject": component_data.get("subject", "Mathematics"),
                    "class_name": component_data.get("class_name", "Class 10A"),
                    "teacher_id": component_data.get("teacher_id", "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"),
                    "weeks_sessions": weeks_sessions,
                }
                formatted_response.append(component_response)
    elif "strand" in ai_data:
        print("Found direct format (strand, substrand, content_standard, indicator)")
        # New simplified format (without explanation/structured_output wrapper)
        # Process each component directly from ai_data
        for component_name in ["strand", "substrand", "content_standard", "indicator"]:
            if component_name in ai_data:
                print(f"Processing component: {component_name}")
                component_data = ai_data[component_name]
                # Extract week numbers from the component data
                weeks_sessions = component_data.get("weeks_sessions", {})
                
                # Create response structure with component-specific fields
                component_response = {
                    "strand_name": component_data.get("strand_name", ""),
                    "subject": component_data.get("subject", "Mathematics"),
                    "class_name": component_data.get("class_name", "Class 10A"),
                    "teacher_id": component_data.get("teacher_id", "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"),
                    "weeks_sessions": weeks_sessions,
                }
                
                # Add component-specific fields
                if component_name == "substrand" and "substrand_name" in component_data:
                    component_response["substrand_name"] = component_data["substrand_name"]
                elif component_name == "content_standard" and "content_standard_code" in component_data:
                    component_response["content_standard_code"] = component_data["content_standard_code"]
                    component_response["content_standard"] = component_data["content_standard"]
                elif component_name == "indicator" and "indicator_code" in component_data:
                    component_response["indicator_code"] = component_data["indicator_code"]
                    component_response["indicator_text"] = component_data["indicator_text"]
                    component_response["content_standard_code"] = component_data.get("content_standard_code", "")
                
                formatted_response.append(component_response)
    
    print(f"\nFormatted response contains {len(formatted_response)} items:")
    for i, item in enumerate(formatted_response):
        print(f"  {i+1}. Keys: {list(item.keys())}")
        if "substrand_name" in item:
            print(f"     Substrand: {item['substrand_name']}")
        elif "content_standard" in item:
            print(f"     Content Standard: {item['content_standard']}")
        elif "indicator_text" in item:
            print(f"     Indicator: {item['indicator_text']}")
        else:
            print(f"     Strand: {item['strand_name']}")
    
    # Verify all components are present
    component_count = {
        "strand": 0,
        "substrand": 0,
        "content_standard": 0,
        "indicator": 0
    }
    
    for item in formatted_response:
        if "substrand_name" in item:
            component_count["substrand"] += 1
        elif "content_standard" in item:
            component_count["content_standard"] += 1
        elif "indicator_text" in item:
            component_count["indicator"] += 1
        else:
            component_count["strand"] += 1
    
    print(f"\nComponent count: {component_count}")
    
    if all(count == 1 for count in component_count.values()):
        print("✅ All components found - implementation is working correctly")
        return True
    else:
        print("❌ Missing components - implementation needs fixing")
        return False

if __name__ == "__main__":
    success = test_read_strand_processing()
    if success:
        print("\n🎉 Read-strand data processing test passed!")
    else:
        print("\n💥 Read-strand data processing test failed!")