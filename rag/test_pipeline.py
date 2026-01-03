#!/usr/bin/env python3
"""
Test script for the document processing pipeline with embeddings and database integration.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rag.pipeline import process_document

async def test_pipeline_with_embeddings():
    """Test the document processing pipeline with embeddings and database integration."""
    print("Testing document processing pipeline with embeddings...")
    
    # Path to the PDF file
    pdf_file_name = "A taxonomy for learning, teaching, and assessing.pdf"
    file_path = os.path.join(project_root, pdf_file_name)
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        return False
    
    try:
        print(f"File exists: {file_path}")
        print("Pipeline module imported successfully")
        
        # Test the complete pipeline with database storage
        print("Testing complete document processing pipeline with database storage...")
        result = await process_document(
            file_path=file_path,
            subject="Educational Taxonomy",
            notes="Test document for RAG pipeline",
            max_tokens=500,
            store_in_db=True
        )
        
        print(f"   ✅ Pipeline processed document successfully")
        print(f"   📊 Chunks created: {result['chunks_count']}")
        print(f"   🧠 Embeddings generated: {result['embeddings_count']}")
        print(f"   💾 Stored in database: {result['stored_in_db']}")
        if result['stored_in_db']:
            print(f"   🆔 Knowledge ID: {result['knowledge_id']}")
        
        print("\n🎉 Pipeline test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_pipeline_with_embeddings())
    if not result:
        sys.exit(1)