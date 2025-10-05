#!/usr/bin/env python3
"""
Test script to verify calendar_back.py imports correctly
"""

def test_calendar_import():
    """Test if calendar_back.py can be imported without errors"""
    print("Testing calendar_back.py import...")
    
    try:
        import sys
        import os
        # Add the parent directory to the path
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, parent_dir)
        
        # Try to import the module
        import ca_ground.calendar_back
        print("✓ calendar_back.py imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import calendar_back.py: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_calendar_import()
    if success:
        print("\n🎉 Calendar import test passed!")
    else:
        print("\n❌ Calendar import test failed!")