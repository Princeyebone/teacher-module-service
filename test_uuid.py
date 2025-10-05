#!/usr/bin/env python3
"""
Test script to verify UUID import and functionality
"""

def test_uuid_import():
    """Test if UUID is properly imported and working"""
    print("Testing UUID import...")
    
    # Try to import UUID
    try:
        from uuid import UUID
        print("✓ UUID imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import UUID: {e}")
        return False
    
    # Try to create a UUID object
    try:
        test_uuid = UUID('12345678-1234-1234-1234-123456789012')
        print(f"✓ UUID creation successful: {test_uuid}")
        return True
    except Exception as e:
        print(f"✗ Failed to create UUID: {e}")
        return False

if __name__ == "__main__":
    success = test_uuid_import()
    if success:
        print("\n🎉 UUID test passed!")
    else:
        print("\n❌ UUID test failed!")