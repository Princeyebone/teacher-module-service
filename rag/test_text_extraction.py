#!/usr/bin/env python3
"""
Test script to verify text extraction functionality.
"""

import os
import sys
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_text_extraction():
    """Test the text extraction functionality."""
    try:
        # Import the text extraction module
        from rag.text import process_all_evaluation_pdfs
        
        print("🧪 Testing text extraction and storage...")
        await process_all_evaluation_pdfs()
        print("✅ Text extraction test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Text extraction test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Running text extraction test...")
    success = asyncio.run(test_text_extraction())
    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)