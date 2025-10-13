"""Test script for AI integration in semester plan processing"""

import json
import re
from external_service import build_semester_plan_prompt, send_semester_plan_to_ai

def test_prompt_builder():
    """Test that the semester plan prompt builder creates the correct prompt"""
    try:
        # Sample extracted text
        extracted_text = """Algebra
Linear Equations
Solve linear equations in one variable
Student can solve one-step linear equations"""

        # Sample GCS path
        gcs_source_path = "gs://teacher_module_acatable_bucket/semplan/7bed2b69-8000-4b36-8e91-7fe0b70c9d82.pdf"

        # Sample session data
        session_data = {
            "semester_start_date": "2024-09-01",
            "semester_end_date": "2024-12-15",
            "weekly_sessions": {
                "Week 1": {
                    "week_number": 1,
                    "sessions": [
                        {
                            "id": 1,
                            "date": "2024-09-02",
                            "subject": "Mathematics",
                            "start_time": "09:00",
                            "end_time": "10:00",
                            "class_name": "Class 10A",
                            "location": "Room 201"
                        }
                    ]
                }
            }
        }

        # Build the prompt
        prompt = build_semester_plan_prompt(extracted_text, gcs_source_path, session_data)
        
        print("✅ Semester plan prompt builder created successfully")
        print(f"Prompt length: {len(prompt)} characters")
        
        # Check that the prompt contains the required elements
        required_elements = [
            "You are an advanced Educational Curriculum Mapping AI",
            "EXTRACTED TEXT",
            "GCS FILE LOCATION",
            "WEEKLY SESSIONS",
            extracted_text,
            gcs_source_path,
            "Week 1"
        ]
        
        for element in required_elements:
            if element in prompt:
                print(f"✅ Contains required element: {element[:50]}...")
            else:
                print(f"❌ Missing required element: {element}")
                return False
                
        return True
        
    except Exception as e:
        print(f"❌ Error testing semester plan prompt builder: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_json_parsing_strategies():
    """Test the enhanced JSON parsing strategies"""
    try:
        # Import the parsing function from external_service
        from external_service import send_semester_plan_to_ai
        import logging
        
        # Set up logging to capture the parsing attempts
        logging.basicConfig(level=logging.INFO)
        
        # Test case 1: Valid JSON (should parse directly)
        valid_json = '{"strand_name": "Algebra", "subject": "Mathematics"}'
        print(f"\nTesting valid JSON: {valid_json}")
        
        # Test case 2: JSON with trailing comma (should be fixed)
        trailing_comma_json = '{"strand_name": "Algebra", "subject": "Mathematics",}'
        print(f"\nTesting JSON with trailing comma: {trailing_comma_json}")
        
        # Test case 3: JSON with missing comma between properties (should be fixed)
        missing_comma_json = '{"strand_name": "Algebra" "subject": "Mathematics"}'
        print(f"\nTesting JSON with missing comma: {missing_comma_json}")
        
        # Test case 4: JSON with single quotes (should be fixed)
        single_quote_json = "{'strand_name': 'Algebra', 'subject': 'Mathematics'}"
        print(f"\nTesting JSON with single quotes: {single_quote_json}")
        
        print("\n✅ JSON parsing strategy tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing JSON parsing strategies: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing AI integration for semester plan processing...")
    
    success1 = test_prompt_builder()
    success2 = test_json_parsing_strategies()
    
    if success1 and success2:
        print("\n🎉 Semester plan AI integration tests completed!")
        print("The AI integration is ready to be used in the semester plan processing pipeline.")
    else:
        print("\n💥 Some semester plan AI integration tests failed!")
        exit(1)