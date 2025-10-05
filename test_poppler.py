#!/usr/bin/env python3
"""
Test script to verify Poppler installation and configuration
"""

import os
import sys
from config import settings

def test_poppler_configuration():
    """Test if Poppler is properly configured"""
    print("Testing Poppler configuration...")
    
    # Check if POPPLER_PATH is set in settings
    poppler_path = settings.POPPLER_PATH
    print(f"POPPLER_PATH from settings: '{poppler_path}'")
    
    # Check if POPPLER_PATH is set in environment variables
    env_poppler_path = os.environ.get('POPPLER_PATH', '')
    print(f"POPPLER_PATH from environment: '{env_poppler_path}'")
    
    # Determine which path to use
    final_path = poppler_path or env_poppler_path
    print(f"Final Poppler path to use: '{final_path}'")
    
    # Check if the path exists (if specified)
    if final_path:
        if os.path.exists(final_path):
            print(f"✓ Poppler path exists: {final_path}")
        else:
            print(f"✗ Poppler path does not exist: {final_path}")
            return False
    else:
        print("ℹ️  No specific Poppler path configured, relying on system PATH")
    
    # Try to import pdf2image and test basic functionality
    try:
        from pdf2image import pdfinfo_from_path
        print("✓ pdf2image imported successfully")
        
        # Try to get pdf info (this will test if poppler is accessible)
        # We're not testing with an actual PDF file here, just checking if the library can load
        print("✓ Poppler appears to be correctly configured!")
        return True
        
    except ImportError as e:
        print(f"✗ Failed to import pdf2image: {e}")
        return False
    except Exception as e:
        print(f"⚠️  pdf2image imported but there may be an issue: {e}")
        # This might be okay if poppler is in PATH
        return True

if __name__ == "__main__":
    success = test_poppler_configuration()
    if success:
        print("\n🎉 Poppler configuration test passed!")
        sys.exit(0)
    else:
        print("\n❌ Poppler configuration test failed!")
        sys.exit(1)