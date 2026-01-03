#!/usr/bin/env python3
"""
Test script for the RAG retrieval functionality.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the retrieval function
from rag.retrievals import search_knowledge, QueryRequest

async def test_retrieval():
    """Test the retrieval functionality."""
    print("Testing RAG retrieval functionality...")
    
    try:
        # Create a test query request
        query_request = QueryRequest(
            query="What is educational taxonomy?",
            subject="Educational Taxonomy",
            limit=5
        )
        
        print(f"Query: {query_request.query}")
        print(f"Subject: {query_request.subject}")
        print(f"Limit: {query_request.limit}")
        
        # Note: We can't easily test the full retrieval without a database connection
        # and pre-populated embeddings. This test is primarily to verify that the
        # module can be imported and the function signatures are correct.
        
        print("✅ Retrieval module imported successfully")
        print("✅ Query request created successfully")
        print("ℹ️  Note: Full retrieval test requires database with embeddings")
        
        return True
        
    except Exception as e:
        print(f"❌ Retrieval test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_retrieval())
    if not result:
        sys.exit(1)