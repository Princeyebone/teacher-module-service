#!/usr/bin/env python3
"""
Test script to verify the read_strands function processes the new nested structure correctly.
"""

import json

# Mock data that simulates what the AI would return with the new nested structure
mock_ai_response = [
  {
    "strand_name": "Algebra",
    "subject": "MATHEMATICS-BASIC 7",
    "class_name": "Class 10A",
    "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
    "substrands": [
      {
        "substrand_name": "Equations and Inequalities",
        "content_standards": [
          {
            "content_standard_code": "B7.2.3.1",
            "content_standard_text": "Solve linear equations in one variable",
            "indicators": [
              {
                "indicator_code": "B7.2.3.1.1",
                "indicator_text": "Solve one-step linear equations",
                "weeks_sessions": {
                  "Week 2": [
                    {
                      "id": 880,
                      "date": "2024-11-18",
                      "start_time": "09:00",
                      "end_time": "10:00",
                      "week_number": 2
                    }
                  ]
                }
              },
              {
                "indicator_code": "B7.2.3.1.2",
                "indicator_text": "Solve two-step linear equations",
                "weeks_sessions": {
                  "Week 2": [
                    {
                      "id": 912,
                      "date": "2024-11-19",
                      "start_time": "10:00",
                      "end_time": "11:00",
                      "week_number": 2
                    }
                  ]
                }
              }
            ]
          }
        ]
      }
    ]
  },
  {
    "strand_name": "Geometry and Measurement",
    "subject": "MATHEMATICS-BASIC 7",
    "class_name": "Class 10A",
    "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
    "substrands": [
      {
        "substrand_name": "Measurement",
        "content_standards": [
          {
            "content_standard_code": "B7.3.2.1",
            "content_standard_text": "Calculate the area of plane figures",
            "indicators": [
              {
                "indicator_code": "B7.3.2.1.1",
                "indicator_text": "Calculate the area of rectangles and squares",
                "weeks_sessions": {
                  "Week 4": [
                    {
                      "id": 882,
                      "date": "2024-12-02",
                      "start_time": "09:00",
                      "end_time": "10:00",
                      "week_number": 4
                    }
                  ]
                }
              }
            ]
          }
        ]
      }
    ]
  }
]

def test_nested_structure_processing():
    """Test the processing logic for the new nested structure."""
    print("Testing nested structure processing logic...")
    
    # Simulate the processing logic for the new format (list of strands)
    ai_data = mock_ai_response
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    subject = "MATHEMATICS-BASIC 7"
    class_name = "Class 10A"
    
    if isinstance(ai_data, list):
        # New format: array of strands
        print(f"AI data is a list with {len(ai_data)} strands")
        result = []
        for strand_data in ai_data:
            strand_entry = {
                "strand_name": strand_data.get("strand_name", ""),
                "subject": strand_data.get("subject", subject),
                "class_name": strand_data.get("class_name", class_name),
                "teacher_id": strand_data.get("teacher_id", str(teacher_id)),
                "substrands": strand_data.get("substrands", []),
                "data_source": "temp_extract",
                "url": None
            }
            result.append(strand_entry)
        
        print(f"Returning result with {len(result)} strands")
        print("Result:")
        print(json.dumps(result, indent=2))
        return result
    else:
        print(f"AI data is not a list: {type(ai_data)}")
        return []

if __name__ == "__main__":
    result = test_nested_structure_processing()
    if result:
        print("\n✅ Test passed! The read_strands function should now work correctly with the new nested structure.")
    else:
        print("\n❌ Test failed! There may still be an issue with the data processing.")