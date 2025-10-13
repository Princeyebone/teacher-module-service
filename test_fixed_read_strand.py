"""Test script to verify the fixed read-strand implementation"""

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

# Mock AI data structure that matches the actual format
mock_ai_data_actual = {
    "strand": {
        "strand_name": "Algebra",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 2
                }
            ]
        }
    },
    "strand_2": {
        "strand_name": "Geometry and Measurement",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 881,
                    "date": "2024-12-02",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 4
                }
            ]
        }
    },
    "substrand": {
        "strand_name": "Algebra",
        "substrand_name": "Equations and Inequalities",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 2
                }
            ]
        }
    },
    "substrand_2": {
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 881,
                    "date": "2024-12-02",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 4
                }
            ]
        }
    },
    "content_standard": {
        "strand_name": "Algebra",
        "substrand_name": "Equations and Inequalities",
        "content_standard_code": "B7.2.3.1",
        "content_standard": "B7.2.3.1",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 2
                }
            ]
        }
    },
    "content_standard_2": {
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "content_standard_code": "B7.3.2.2",
        "content_standard": "B7.3.2.2",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 5": [
                {
                    "id": 882,
                    "date": "2024-12-02",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 5
                }
            ]
        }
    },
    "indicator": {
        "strand_name": "Algebra",
        "substrand_name": "Equations and Inequalities",
        "content_standard_code": "B7.2.3.1",
        "indicator_code": "B7.2.3.1.1",
        "indicator_text": "B7.2.3.1.1",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 2
                }
            ]
        }
    },
    "indicator_2": {
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "content_standard_code": "B7.3.2.2",
        "indicator_code": "B7.3.2.2.1",
        "indicator_text": "B7.3.2.2.1",
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "weeks_sessions": {
            "Week 5": [
                {
                    "id": 882,
                    "date": "2024-12-02",
                    "subject": "Mathematics",
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "class_name": "Class 10A",
                    "location": "Class 10A",
                    "week_number": 5
                }
            ]
        }
    }
}

def process_tempextract_data_fixed(temp_entry, subject, class_name, teacher_id):
    """Simulate the FIXED processing logic from read_strands endpoint"""
    if temp_entry and temp_entry.data:
        # Format the data to match the StrandResponse structure
        ai_data = temp_entry.data
        formatted_response = []
        
        # Handle the actual format returned by AI which uses numbered keys
        if isinstance(ai_data, dict):
            # Look for all strand components (strand, strand_2, strand_3, etc.)
            strand_keys = [k for k in ai_data.keys() if k == 'strand' or k.startswith('strand_')]
            
            # Look for all substrand components
            substrand_keys = [k for k in ai_data.keys() if k == 'substrand' or k.startswith('substrand')]
            
            # Look for all content_standard components
            content_standard_keys = [k for k in ai_data.keys() if k == 'content_standard' or k.startswith('content_standard')]
            
            # Look for all indicator components
            indicator_keys = [k for k in ai_data.keys() if k == 'indicator' or k.startswith('indicator')]
            
            # Process all strand components
            for key in strand_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file
                    }
                    formatted_response.append(component_response)
            
            # Process all substrand components
            for key in substrand_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file
                    }
                    
                    # Add substrand-specific fields
                    if "substrand_name" in component_data:
                        component_response["substrand_name"] = component_data["substrand_name"]
                        
                    formatted_response.append(component_response)
            
            # Process all content_standard components
            for key in content_standard_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file
                    }
                    
                    # Add content_standard-specific fields
                    if "content_standard_code" in component_data:
                        component_response["content_standard_code"] = component_data["content_standard_code"]
                    if "content_standard" in component_data:
                        component_response["content_standard"] = component_data["content_standard"]
                        
                    formatted_response.append(component_response)
            
            # Process all indicator components
            for key in indicator_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file
                    }
                    
                    # Add indicator-specific fields
                    if "indicator_code" in component_data:
                        component_response["indicator_code"] = component_data["indicator_code"]
                    if "indicator_text" in component_data:
                        component_response["indicator_text"] = component_data["indicator_text"]
                    if "content_standard_code" in component_data:
                        component_response["content_standard_code"] = component_data["content_standard_code"]
                        
                    formatted_response.append(component_response)
        
        return formatted_response
    return []

def test_fixed_implementation():
    """Test the fixed implementation"""
    print("Testing FIXED read-strand implementation...")
    
    temp_entry = MockTempExtract(mock_ai_data_actual, "https://example.com/file.pdf")
    result = process_tempextract_data_fixed(temp_entry, "Mathematics", "Class 10A", "7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"Processed {len(result)} components:")
    
    # Count different component types
    strand_count = 0
    substrand_count = 0
    content_standard_count = 0
    indicator_count = 0
    
    for item in result:
        if "substrand_name" in item and "content_standard_code" not in item and "indicator_code" not in item:
            substrand_count += 1
            print(f"  Substrand: {item['strand_name']} - {item['substrand_name']}")
        elif "content_standard_code" in item and "indicator_code" not in item:
            content_standard_count += 1
            print(f"  Content Standard: {item['strand_name']} - {item.get('content_standard', 'N/A')}")
        elif "indicator_code" in item:
            indicator_count += 1
            print(f"  Indicator: {item['strand_name']} - {item.get('indicator_text', 'N/A')}")
        else:
            strand_count += 1
            print(f"  Strand: {item['strand_name']}")
    
    print(f"\nComponent breakdown:")
    print(f"  Strands: {strand_count}")
    print(f"  Substrands: {substrand_count}")
    print(f"  Content Standards: {content_standard_count}")
    print(f"  Indicators: {indicator_count}")
    print(f"  Total: {len(result)}")
    
    # Verify we got all components
    expected_total = 8  # 2 strands + 2 substrands + 2 content standards + 2 indicators
    if len(result) == expected_total:
        print("✅ FIXED implementation test passed - all components processed")
        return True
    else:
        print(f"❌ FIXED implementation test failed - expected {expected_total} components, got {len(result)}")
        return False

if __name__ == "__main__":
    print("Testing FIXED read-strand endpoint implementation")
    print("=" * 50)
    
    success = test_fixed_implementation()
    
    if success:
        print("\n🎉 FIXED implementation test passed! Read-strand endpoint should now return all components correctly.")
    else:
        print("\n💥 FIXED implementation test failed! Further investigation needed.")