"""Test script for the timetable prompt builder"""

from external_service import build_timetable_prompt

def test_prompt_builder():
    """Test that the prompt builder creates the correct prompt"""
    try:
        # Sample extracted text
        extracted_text = """MONDAY
09:00-10:00 Mathematics - Class 10A - Room 201
10:00-11:00 English - Class 10A - Room 202

TUESDAY
09:00-10:00 Physics - Class 10A - Room 301
10:00-11:00 Chemistry - Class 10A - Room 302"""

        # Sample GCS path
        gcs_source_path = "gs://teacher_module_acatable_bucket/timetable/7bed2b69-8000-4b36-8e91-7fe0b70c9d82.pdf"

        # Build the prompt
        prompt = build_timetable_prompt(extracted_text, gcs_source_path)
        
        print("✅ Prompt builder created successfully")
        print(f"Prompt length: {len(prompt)} characters")
        
        # Check that the prompt contains the required elements
        required_elements = [
            "You are an advanced AI assistant specializing in processing complex timetable data",
            "EXTRACTED_TEXT",
            "GCS_SOURCE_PATH",
            "Required JSON Output Structure",
            extracted_text,
            gcs_source_path
        ]
        
        for element in required_elements:
            if element in prompt:
                print(f"✅ Contains required element: {element[:50]}...")
            else:
                print(f"❌ Missing required element: {element}")
                return False
                
        # Show a portion of the generated prompt
        print("\nGenerated prompt (first 500 characters):")
        print(prompt[:500] + "...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing prompt builder: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing timetable prompt builder...")
    
    success = test_prompt_builder()
    
    if success:
        print("\n🎉 Prompt builder test passed!")
        print("The prompt builder correctly generates prompts for AI timetable processing.")
    else:
        print("\n💥 Prompt builder test failed!")
        exit(1)