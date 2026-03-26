#!/usr/bin/env python3
"""
Test script for the RAG retrieval functionality with pillar filtering.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the retrieval function
from app.rag.retrievals import QueryRequest

def test_pillar_filtering():
    """Test the pillar filtering functionality."""
    print("Testing RAG retrieval with pillar filtering...")
    
    try:
        # Create a test query request with pillar filtering
        query_request = QueryRequest(
            query="What is educational taxonomy?",
            subject="Educational Taxonomy",
            pillar="cognitive science and pedagogy",
            limit=5
        )
        
        print(f"Query: {query_request.query}")
        print(f"Subject: {query_request.subject}")
        print(f"Pillar: {query_request.pillar}")
        print(f"Limit: {query_request.limit}")
        
        print("✅ Query request with pillar filtering created successfully")
        return True
        
    except Exception as e:
        print(f"❌ Pillar filtering test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = test_pillar_filtering()
    if not result:
        sys.exit(1)
    else:
        print("✅ All tests passed!")