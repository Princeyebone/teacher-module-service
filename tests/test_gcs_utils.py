"""Test script for GCS utilities"""

import os
from app.services.gcs_utils import generate_file_name

def test_generate_file_name():
    """Test the generate_file_name function"""
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
    
    # Test with different file extensions
    test_cases = [
        ("pdf", "timetable/7bed2b69-8000-4b36-8e91-7fe0b70c9d82.pdf"),
        ("docx", "timetable/7bed2b69-8000-4b36-8e91-7fe0b70c9d82.docx"),
        ("xlsx", "timetable/7bed2b69-8000-4b36-8e91-7fe0b70c9d82.xlsx"),
        ("jpg", "timetable/7bed2b69-8000-4b36-8e91-7fe0b70c9d82.jpg"),
    ]
    
    print("Testing generate_file_name function:")
    for ext, expected in test_cases:
        result = generate_file_name(teacher_id, ext)
        if result == expected:
            print(f"✅ {ext}: {result}")
        else:
            print(f"❌ {ext}: Expected {expected}, got {result}")

if __name__ == "__main__":
    test_generate_file_name()
    print("\nNote: Other GCS functions require actual GCS configuration and credentials to test.")