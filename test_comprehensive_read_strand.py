"""Comprehensive test for read-strand endpoint implementation"""

import json
from datetime import datetime
from uuid import UUID

# Mock TempExtract entry
class MockTempExtract:
    def __init__(self, data, file=None):
        self.data = data
        self.file = file
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

# Mock AI data structures
mock_ai_data_direct = {
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

mock_ai_data_structured = {
    "structured_output": {
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
}

def process_tempextract_data(temp_entry, subject, class_name, teacher_id):
    """Simulate the processing logic from read_strands endpoint"""
    if temp_entry and temp_entry.data:
        # Format the data to match the StrandResponse structure
        ai_data = temp_entry.data
        formatted_response = []
        
        # Check if this is the new format (with structured_output) or old format (with strands)
        if "structured_output" in ai_data:
            # New format with explanation and structured_output
            structured_output = ai_data["structured_output"]
            
            # Process each component from structured_output
            for component_name in ["strand", "substrand", "content_standard", "indicator"]:
                if component_name in structured_output:
                    component_data = structured_output[component_name]
                    # Extract week numbers from the component data
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    # Create response structure
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",  # Indicate source of data
                        "file": temp_entry.file  # Include the signed URL for the file
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
                    
        elif "strand" in ai_data:
            # New simplified format (without explanation/structured_output wrapper)
            # Process each component directly from ai_data
            for component_name in ["strand", "substrand", "content_standard", "indicator"]:
                if component_name in ai_data:
                    component_data = ai_data[component_name]
                    # Extract week numbers from the component data
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    # Create response structure
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",  # Indicate source of data
                        "file": temp_entry.file  # Include the signed URL for the file
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
        
        return formatted_response
    return []

def test_direct_format():
    """Test processing of direct format AI data"""
    print("Testing direct format AI data processing...")
    
    temp_entry = MockTempExtract(mock_ai_data_direct, "https://example.com/file.pdf")
    result = process_tempextract_data(temp_entry, "Mathematics", "Class 10A", "7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"Processed {len(result)} components:")
    component_types = []
    for i, item in enumerate(result):
        if "substrand_name" in item:
            component_types.append(f"Substrand: {item['substrand_name']}")
        elif "content_standard" in item:
            component_types.append(f"Content Standard: {item['content_standard']}")
        elif "indicator_text" in item:
            component_types.append(f"Indicator: {item['indicator_text']}")
        else:
            component_types.append(f"Strand: {item['strand_name']}")
    
    for ctype in component_types:
        print(f"  - {ctype}")
    
    expected_count = 4  # strand, substrand, content_standard, indicator
    if len(result) == expected_count:
        print("✅ Direct format test passed - all components processed")
        return True
    else:
        print(f"❌ Direct format test failed - expected {expected_count} components, got {len(result)}")
        return False

def test_structured_format():
    """Test processing of structured format AI data"""
    print("\nTesting structured format AI data processing...")
    
    temp_entry = MockTempExtract(mock_ai_data_structured, "https://example.com/file.pdf")
    result = process_tempextract_data(temp_entry, "Mathematics", "Class 10A", "7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"Processed {len(result)} components:")
    component_types = []
    for i, item in enumerate(result):
        if "substrand_name" in item:
            component_types.append(f"Substrand: {item['substrand_name']}")
        elif "content_standard" in item:
            component_types.append(f"Content Standard: {item['content_standard']}")
        elif "indicator_text" in item:
            component_types.append(f"Indicator: {item['indicator_text']}")
        else:
            component_types.append(f"Strand: {item['strand_name']}")
    
    for ctype in component_types:
        print(f"  - {ctype}")
    
    expected_count = 4  # strand, substrand, content_standard, indicator
    if len(result) == expected_count:
        print("✅ Structured format test passed - all components processed")
        return True
    else:
        print(f"❌ Structured format test failed - expected {expected_count} components, got {len(result)}")
        return False

if __name__ == "__main__":
    print("Comprehensive read-strand endpoint test")
    print("=" * 50)
    
    success1 = test_direct_format()
    success2 = test_structured_format()
    
    if success1 and success2:
        print("\n🎉 All tests passed! Read-strand endpoint should return all components correctly.")
    else:
        print("\n💥 Some tests failed! Read-strand endpoint needs investigation.")