"""Test script for the improved semester plan prompt with session mapping"""

import json
from external_service import build_semester_plan_prompt

def test_session_mapping_prompt():
    """Test that the prompt clearly instructs AI to use actual session data"""
    try:
        # Sample extracted text
        extracted_text = """Algebra
Linear Equations
Solve linear equations in one variable
Student can solve one-step linear equations"""

        # Sample GCS path
        gcs_source_path = "gs://teacher_module_acatable_bucket/semplan/7bed2b69-8000-4b36-8e91-7fe0b70c9d82.pdf"

        # Sample session data with actual session details
        session_data = {
            "semester_start_date": "2024-09-01",
            "semester_end_date": "2024-12-15",
            "weekly_sessions": {
                "Week 2": {
                    "week_number": 2,
                    "sessions": [
                        {
                            "id": 880,
                            "date": "2024-09-09",
                            "subject": "Mathematics",
                            "start_time": "09:00",
                            "end_time": "10:00",
                            "class_name": "Class 10A",
                            "location": "Room 201",
                            "session_number": 1
                        },
                        {
                            "id": 881,
                            "date": "2024-09-09",
                            "subject": "Mathematics",
                            "start_time": "10:00",
                            "end_time": "11:00",
                            "class_name": "Class 10A",
                            "location": "Room 201",
                            "session_number": 2
                        }
                    ]
                },
                "Week 3": {
                    "week_number": 3,
                    "sessions": [
                        {
                            "id": 882,
                            "date": "2024-09-16",
                            "subject": "Mathematics",
                            "start_time": "09:00",
                            "end_time": "10:00",
                            "class_name": "Class 10A",
                            "location": "Room 201",
                            "session_number": 3
                        }
                    ]
                }
            }
        }

        # Build the prompt
        prompt = build_semester_plan_prompt(extracted_text, gcs_source_path, session_data)
        
        print("✅ Semester plan prompt with session mapping created successfully")
        print(f"Prompt length: {len(prompt)} characters")
        
        # Check that the prompt contains key instructions about using actual session data
        required_instructions = [
            "COPY EXACT session details",
            "USE THOSE EXACT VALUES",
            "COPY session details from WeeklySessions EXACTLY",
            "no null values"
        ]
        
        missing_instructions = []
        for instruction in required_instructions:
            if instruction in prompt:
                print(f"✅ Contains instruction: {instruction}")
            else:
                missing_instructions.append(instruction)
                print(f"❌ Missing instruction: {instruction}")
        
        if missing_instructions:
            print(f"❌ Missing required instructions: {missing_instructions}")
            return False
            
        # Check that the prompt contains the actual session data
        session_indicators = [
            "id: 880",
            "date: 2024-09-09",
            "start_time: 09:00",
            "end_time: 10:00"
        ]
        
        missing_session_data = []
        for indicator in session_indicators:
            if indicator in prompt:
                print(f"✅ Contains session data: {indicator}")
            else:
                missing_session_data.append(indicator)
                print(f"❌ Missing session data: {indicator}")
        
        if missing_session_data:
            print(f"❌ Missing session data indicators: {missing_session_data}")
            return False
            
        # Check that the prompt is clear about the task
        task_indicators = [
            "COPY EXACT session details",
            "Map these elements linearly",
            "USE THOSE EXACT VALUES"
        ]
        
        missing_task_indicators = []
        for indicator in task_indicators:
            if indicator in prompt:
                print(f"✅ Contains task indicator: {indicator}")
            else:
                missing_task_indicators.append(indicator)
                print(f"❌ Missing task indicator: {indicator}")
        
        if missing_task_indicators:
            print(f"❌ Missing task indicators: {missing_task_indicators}")
            return False
                
        return True
        
    except Exception as e:
        print(f"❌ Error testing session mapping prompt: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing semester plan prompt with session mapping...")
    
    success = test_session_mapping_prompt()
    
    if success:
        print("\n🎉 Session mapping prompt test completed!")
        print("The prompt clearly instructs the AI to use actual session data.")
    else:
        print("\n💥 Session mapping prompt test failed!")
        exit(1)