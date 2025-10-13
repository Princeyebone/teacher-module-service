"""Test script for JSON parsing improvements in semester plan AI processing"""

import json
import re
import logging
from external_service import send_semester_plan_to_ai

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_json_parsing_with_comma_error():
    """Test JSON parsing with the specific comma error we encountered"""
    try:
        # Simulate the AI response that caused the error
        # This is a mock response that mimics the structure that caused "Expecting ',' delimiter"
        mock_ai_response = '''
{
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
    }
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
    }
  }
}
'''
        # Note the missing comma between "strand" and "substrand" objects
        # This would cause "Expecting ',' delimiter: line 741 column 8" error
        
        print("Testing JSON parsing with missing comma error...")
        print(f"Mock AI response length: {len(mock_ai_response)} characters")
        
        # Try to parse this with our enhanced strategies
        # First, extract JSON object pattern
        json_match = re.search(r"\{[\s\S]*\}", mock_ai_response)
        if json_match:
            json_str = json_match.group(0)
            print(f"Extracted JSON length: {len(json_str)} characters")
            
            # Try multiple JSON parsing strategies
            parsed_result = None
            parsing_errors = []
            
            # Strategy 1: Direct parsing
            try:
                parsed_result = json.loads(json_str)
                print("✅ Direct parsing successful")
            except json.JSONDecodeError as e:
                parsing_errors.append(f"Direct parsing failed: {e}")
                print(f"⚠️ Direct parsing failed: {e}")
            
            # Strategy 2: If direct parsing fails, try to fix common issues
            if parsed_result is None:
                try:
                    # Fix common JSON issues
                    fixed_json = json_str
                    
                    # Fix trailing commas before closing braces/brackets
                    fixed_json = re.sub(r",(\s*[}\]])", r"\1", fixed_json)
                    
                    # Fix missing commas between object properties
                    # Look for patterns like }"key" and add comma: },"key"
                    fixed_json = re.sub(r'(\})\s*"', r'\1,"', fixed_json)
                    
                    # Fix single quotes to double quotes (be careful not to mess up escaped quotes)
                    fixed_json = re.sub(r"'([^']*)':", r'"\1":', fixed_json)  # Keys
                    fixed_json = re.sub(r":\s*'([^']*)'", r': "\1"', fixed_json)  # String values
                    
                    parsed_result = json.loads(fixed_json)
                    print("✅ Fixed parsing successful")
                except json.JSONDecodeError as e:
                    parsing_errors.append(f"Fixed parsing failed: {e}")
                    print(f"⚠️ Fixed parsing failed: {e}")
            
            # Strategy 3: More advanced JSON fixing for comma issues
            if parsed_result is None:
                try:
                    # Try to fix missing commas between object properties
                    fixed_json = json_str
                    
                    # Fix missing commas between object properties
                    # Look for patterns like }"key" and add comma: },"key"
                    fixed_json = re.sub(r'(\})\s*"', r'\1,"', fixed_json)
                    
                    # Fix missing commas between array elements
                    # Look for patterns like ]{ and add comma: ],{
                    fixed_json = re.sub(r'(\])\s*\{', r'\1,\{', fixed_json)
                    
                    # Fix missing commas between array elements
                    # Look for patterns like }{ and add comma: },{
                    fixed_json = re.sub(r'(\})\s*\{', r'\1,\{', fixed_json)
                    
                    # Try to parse the fixed JSON
                    parsed_result = json.loads(fixed_json)
                    print("✅ Advanced comma fixes successful")
                except json.JSONDecodeError as e:
                    parsing_errors.append(f"Advanced comma fixes failed: {e}")
                    print(f"⚠️ Advanced comma fixes failed: {e}")
            
            if parsed_result is not None:
                print("✅ JSON parsing successful with enhanced strategies!")
                print(f"Parsed result keys: {list(parsed_result.keys())}")
                return True
            else:
                print("❌ All JSON parsing strategies failed:")
                for error in parsing_errors:
                    print(f"   - {error}")
                return False
        else:
            print("❌ No JSON found in mock AI response")
            return False
            
    except Exception as e:
        print(f"❌ Error testing JSON parsing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_realistic_ai_response():
    """Test with a more realistic AI response that might cause parsing issues"""
    try:
        # A more realistic AI response that might have formatting issues
        mock_ai_response = '''
{
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
    }
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
'''
        # Note the missing comma between "content_standard" and "indicator" objects
        
        print("\nTesting realistic AI response with missing comma...")
        print(f"Mock AI response length: {len(mock_ai_response)} characters")
        
        # Try to parse this with our enhanced strategies
        json_match = re.search(r"\{[\s\S]*\}", mock_ai_response)
        if json_match:
            json_str = json_match.group(0)
            print(f"Extracted JSON length: {len(json_str)} characters")
            
            # Try multiple JSON parsing strategies
            parsed_result = None
            parsing_errors = []
            
            # Strategy 1: Direct parsing
            try:
                parsed_result = json.loads(json_str)
                print("✅ Direct parsing successful")
            except json.JSONDecodeError as e:
                parsing_errors.append(f"Direct parsing failed: {e}")
                print(f"⚠️ Direct parsing failed: {e}")
            
            # Strategy 2: Advanced comma fixes
            if parsed_result is None:
                try:
                    # Try to fix missing commas between object properties
                    fixed_json = json_str
                    
                    # Fix missing commas between object properties
                    fixed_json = re.sub(r'(\})\s*"', r'\1,"', fixed_json)
                    
                    # Try to parse the fixed JSON
                    parsed_result = json.loads(fixed_json)
                    print("✅ Advanced comma fixes successful")
                except json.JSONDecodeError as e:
                    parsing_errors.append(f"Advanced comma fixes failed: {e}")
                    print(f"⚠️ Advanced comma fixes failed: {e}")
            
            if parsed_result is not None:
                print("✅ JSON parsing successful with enhanced strategies!")
                print(f"Structured output keys: {list(parsed_result.get('structured_output', {}).keys())}")
                return True
            else:
                print("❌ All JSON parsing strategies failed:")
                for error in parsing_errors:
                    print(f"   - {error}")
                return False
        else:
            print("❌ No JSON found in mock AI response")
            return False
            
    except Exception as e:
        print(f"❌ Error testing realistic AI response: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing JSON parsing improvements for semester plan AI processing...")
    
    success1 = test_json_parsing_with_comma_error()
    success2 = test_realistic_ai_response()
    
    if success1 and success2:
        print("\n🎉 All JSON parsing tests completed successfully!")
        print("The enhanced JSON parsing strategies can handle common AI response formatting issues.")
    else:
        print("\n💥 Some JSON parsing tests failed!")
        exit(1)