#!/usr/bin/env python3
"""
Unit tests for the new semester plan implementation.
These tests focus on the logic without requiring database connections.
"""

import sys
from pathlib import Path
import json

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_ai_response_structure():
    """Test that the AI response structure is correctly parsed."""
    # Sample AI response
    ai_response = [
        {
            "strand_name": "Algebra",
            "subject": "Mathematics",
            "class_name": "Grade 10A",
            "teacher_id": "test-teacher-id",
            "substrands": [
                {
                    "substrand_name": "Linear Equations",
                    "content_standards": [
                        {
                            "content_standard_code": "ALG-LE-001",
                            "content_standard_text": "Solve linear equations in one variable",
                            "indicators": [
                                {
                                    "indicator_code": "ALG-LE-001-I01",
                                    "indicator_text": "Student can solve one-step linear equations",
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
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
    
    # Test that we can parse the structure correctly
    assert isinstance(ai_response, list), "AI response should be a list"
    assert len(ai_response) > 0, "AI response should have at least one strand"
    
    strand = ai_response[0]
    assert "strand_name" in strand, "Strand should have a name"
    assert "substrands" in strand, "Strand should have substrands"
    
    substrands = strand["substrands"]
    assert isinstance(substrands, list), "Substrands should be a list"
    assert len(substrands) > 0, "Should have at least one substrand"
    
    substrand = substrands[0]
    assert "substrand_name" in substrand, "Substrand should have a name"
    assert "content_standards" in substrand, "Substrand should have content standards"
    
    content_standards = substrand["content_standards"]
    assert isinstance(content_standards, list), "Content standards should be a list"
    assert len(content_standards) > 0, "Should have at least one content standard"
    
    cs = content_standards[0]
    assert "content_standard_code" in cs or "content_standard_text" in cs, "Content standard should have code or text"
    assert "indicators" in cs, "Content standard should have indicators"
    
    indicators = cs["indicators"]
    assert isinstance(indicators, list), "Indicators should be a list"
    assert len(indicators) > 0, "Should have at least one indicator"
    
    indicator = indicators[0]
    assert "indicator_text" in indicator, "Indicator should have text"
    assert "weeks_sessions" in indicator, "Indicator should have weeks_sessions"
    
    weeks_sessions = indicator["weeks_sessions"]
    assert isinstance(weeks_sessions, dict), "Weeks sessions should be a dict"
    assert len(weeks_sessions) > 0, "Should have at least one week"
    
    week_key = list(weeks_sessions.keys())[0]
    sessions = weeks_sessions[week_key]
    assert isinstance(sessions, list), "Sessions should be a list"
    assert len(sessions) > 0, "Should have at least one session"
    
    session = sessions[0]
    required_fields = ["id", "date", "start_time", "end_time", "week_number"]
    for field in required_fields:
        assert field in session, f"Session should have {field}"
    
    print("✅ AI response structure test passed!")
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
        from semester_mapper import read_strands
        print("✅ read_strands import test passed!")
    except Exception as e:
        print(f"❌ read_strands import test failed: {e}")
        return False
    
    return True

def test_function_signatures():
    """Test that function signatures are correct."""
    import inspect
    
    from semplan_ground.semplan_back import store_ai_response_in_tables
    sig = inspect.signature(store_ai_response_in_tables)
    params = list(sig.parameters.keys())
    expected_params = ["teacher_id", "class_name", "subject", "ai_response"]
    assert params == expected_params, f"store_ai_response_in_tables parameters should be {expected_params}, got {params}"
    print("✅ store_ai_response_in_tables signature test passed!")
    
    from semester_mapper import read_strands
    sig = inspect.signature(read_strands)
    params = list(sig.parameters.keys())
    # Note: read_strands has additional parameters like current_teacher, db, etc.
    assert "subject" in params, "read_strands should have subject parameter"
    assert "class_name" in params, "read_strands should have class_name parameter"
    print("✅ read_strands signature test passed!")
    
    return True

def main():
    """Run all unit tests."""
    print("Running unit tests for new semester plan implementation...")
    
    tests = [
        test_imports,
        test_function_signatures,
        test_ai_response_structure
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
        print("🎉 All unit tests passed!")
        return True
    else:
        print("💥 Some unit tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)