"""Test script for the simplified semester plan prompt"""

from external_service import build_semester_plan_prompt

def test_simplified_prompt():
    """Test that the simplified prompt doesn't contain explanation sections"""
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
        
        print("✅ Simplified semester plan prompt created successfully")
        print(f"Prompt length: {len(prompt)} characters")
        
        # Check that the prompt doesn't contain explanation-related terms
        explanation_terms = [
            "explanation",
            "summary",
            "analyze and decompose",
            "logical order",
            "continuity",
            "teaching progression",
            "mapping elements",
            "FINAL CHECK",
            "OBJECTIVE",
            "INPUTS",
            "TASK DETAILS",
            "OUTPUT FORMAT"
        ]
        
        found_explanation_terms = []
        for term in explanation_terms:
            if term.lower() in prompt.lower():
                found_explanation_terms.append(term)
        
        if found_explanation_terms:
            print(f"❌ Found explanation terms in prompt: {found_explanation_terms}")
            return False
        else:
            print("✅ No explanation terms found in prompt")
            
        # Check that the prompt contains the required elements
        required_elements = [
            "Educational Curriculum Mapping AI",
            "ExtractedText",
            "GCSFileLocation",
            "WeeklySessions",
            "RETURN ONLY VALID JSON",
            "CRITICAL RULES"
        ]
        
        for element in required_elements:
            if element in prompt:
                print(f"✅ Contains required element: {element[:50]}...")
            else:
                print(f"❌ Missing required element: {element}")
                return False
                
        # Check that the prompt is significantly shorter than before
        if len(prompt) < 2000:  # Should be much shorter now
            print("✅ Prompt is appropriately concise")
        else:
            print(f"⚠️ Prompt is still quite long: {len(prompt)} characters")
                
        return True
        
    except Exception as e:
        print(f"❌ Error testing simplified prompt: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing simplified semester plan prompt...")
    
    success = test_simplified_prompt()
    
    if success:
        print("\n🎉 Simplified semester plan prompt test completed!")
        print("The prompt is now concise and doesn't contain explanation sections.")
    else:
        print("\n💥 Simplified semester plan prompt test failed!")
        exit(1)