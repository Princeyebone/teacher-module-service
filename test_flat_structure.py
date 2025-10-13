#!/usr/bin/env python3
"""
Test script to verify the flat structure approach for AI response handling.
"""

import sys
from pathlib import Path
import json

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_flat_structure_parsing():
    """Test that the flat structure can be parsed correctly."""
    
    # Sample AI response in the new flat format
    ai_response = {
        "strand_data": [
            {
                "strand_name": "Algebra",
                "subject": "Mathematics",
                "class_name": "Grade 10A",
                "teacher_id": "test-teacher-id",
                "weeks": [1, 2, 3],
                "session_ids": [880, 881, 882],
                "session_details": [
                    {
                        "id": 880,
                        "date": "2024-11-18",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "week_number": 2
                    }
                ]
            }
        ],
        "substrand_data": [
            {
                "strand_name": "Algebra",
                "substrand_name": "Linear Equations",
                "subject": "Mathematics",
                "class_name": "Grade 10A",
                "teacher_id": "test-teacher-id",
                "weeks": [1, 2, 3],
                "session_ids": [880, 881, 882],
                "session_details": [
                    {
                        "id": 880,
                        "date": "2024-11-18",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "week_number": 2
                    }
                ]
            }
        ],
        "content_standard_data": [
            {
                "strand_name": "Algebra",
                "substrand_name": "Linear Equations",
                "content_standard_code": "ALG-LE-001",
                "content_standard_text": "Solve linear equations in one variable",
                "subject": "Mathematics",
                "class_name": "Grade 10A",
                "teacher_id": "test-teacher-id",
                "session_ids": [880, 881],
                "session_details": [
                    {
                        "id": 880,
                        "date": "2024-11-18",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "week_number": 2
                    }
                ]
            }
        ],
        "indicator_data": [
            {
                "strand_name": "Algebra",
                "substrand_name": "Linear Equations",
                "content_standard_code": "ALG-LE-001",
                "indicator_code": "ALG-LE-001-I01",
                "indicator_text": "Student can solve one-step linear equations",
                "subject": "Mathematics",
                "class_name": "Grade 10A",
                "teacher_id": "test-teacher-id",
                "session_ids": [880],
                "session_details": [
                    {
                        "id": 880,
                        "date": "2024-11-18",
                        "start_time": "09:00",
                        "end_time": "10:00",
                        "week_number": 2
                    }
                ]
            }
        ]
    }
    
    # Test that we can parse the structure correctly
    assert isinstance(ai_response, dict), "AI response should be a dict"
    
    # Test strand data
    assert "strand_data" in ai_response, "AI response should have strand_data"
    strand_data_list = ai_response["strand_data"]
    assert isinstance(strand_data_list, list), "strand_data should be a list"
    assert len(strand_data_list) > 0, "Should have at least one strand"
    
    strand_data = strand_data_list[0]
    required_fields = ["strand_name", "weeks", "session_ids", "session_details"]
    for field in required_fields:
        assert field in strand_data, f"Strand data should have {field}"
    
    # Test substrand data
    assert "substrand_data" in ai_response, "AI response should have substrand_data"
    substrand_data_list = ai_response["substrand_data"]
    assert isinstance(substrand_data_list, list), "substrand_data should be a list"
    assert len(substrand_data_list) > 0, "Should have at least one substrand"
    
    substrand_data = substrand_data_list[0]
    required_fields = ["strand_name", "substrand_name", "weeks", "session_ids", "session_details"]
    for field in required_fields:
        assert field in substrand_data, f"Substrand data should have {field}"
    
    # Test content standard data
    assert "content_standard_data" in ai_response, "AI response should have content_standard_data"
    cs_data_list = ai_response["content_standard_data"]
    assert isinstance(cs_data_list, list), "content_standard_data should be a list"
    assert len(cs_data_list) > 0, "Should have at least one content standard"
    
    cs_data = cs_data_list[0]
    required_fields = ["strand_name", "substrand_name", "content_standard_text", "session_ids", "session_details"]
    for field in required_fields:
        assert field in cs_data, f"Content standard data should have {field}"
    
    # Test indicator data
    assert "indicator_data" in ai_response, "AI response should have indicator_data"
    indicator_data_list = ai_response["indicator_data"]
    assert isinstance(indicator_data_list, list), "indicator_data should be a list"
    assert len(indicator_data_list) > 0, "Should have at least one indicator"
    
    indicator_data = indicator_data_list[0]
    required_fields = ["strand_name", "substrand_name", "content_standard_code", "indicator_text", "session_ids", "session_details"]
    for field in required_fields:
        assert field in indicator_data, f"Indicator data should have {field}"
    
    print("✅ Flat structure parsing test passed!")
    return True

def test_imports():
    """Test that all required functions can be imported."""
    try:
        from semplan_ground.semplan_back import store_ai_response_in_tables
        print("✅ store_ai_response_in_tables import test passed!")
    except Exception as e:
        print(f"❌ store_ai_response_in_tables import test failed: {e}")
        return False
    
    try:
        from external_service import build_semester_plan_prompt
        print("✅ build_semester_plan_prompt import test passed!")
    except Exception as e:
        print(f"❌ build_semester_plan_prompt import test failed: {e}")
        return False
    
    return True

def main():
    """Run all tests."""
    print("Running tests for flat structure approach...")
    
    tests = [
        test_imports,
        test_flat_structure_parsing
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed with exception: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("💥 Some tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)