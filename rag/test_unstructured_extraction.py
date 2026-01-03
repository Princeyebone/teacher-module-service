#!/usr/bin/env python3
"""
Test script to verify unstructured.io text extraction functionality.
"""

import os
import sys
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_unstructured_extraction():
    """Test the unstructured.io text extraction functionality."""
    try:
        # Import the unstructured extraction module
        from rag.unstructuredtest import process_all_evaluation_pdfs
        
        print("🧪 Testing unstructured.io text extraction and storage...")
        await process_all_evaluation_pdfs()
        print("✅ Unstructured.io text extraction test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Unstructured.io text extraction test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Running unstructured.io text extraction test...")
    success = asyncio.run(test_unstructured_extraction())
    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)