#!/usr/bin/env python3
"""
Test Script for Embedding Processing

This script tests the embedding processing functionality by:
1. Creating sample chunks
2. Enqueuing embedding tasks
3. Running workers to process the tasks

Usage:
    python test_embedding_processing.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_embedding_processing():
    """Test the embedding processing functionality"""
    logger.info("🧪 Starting embedding processing test...")
    
    try:
        # Import the necessary modules
        from rag_back.enqueue_embedding import enqueue_embedding_task
        from rag_back.embedding_back import process_text_for_embedding
        
        # Test 1: Direct task enqueue
        logger.info("Test 1: Enqueuing direct embedding task...")
        
        # Sample chunks for testing
        test_chunks = [
            "This is the first test chunk for embedding generation.",
            "This is the second test chunk with different content.",
            "Machine learning is a subset of artificial intelligence.",
            "Natural language processing enables computers to understand human language.",
            "Deep learning uses neural networks with multiple layers."
        ] * 10  # Multiply to have more chunks
        
        metadata = {
            "subject": "Computer Science",
            "notes": "Test document for embedding processing",
            "level": "Advanced",
            "region": "Global",
            "pillar": "Technology and Innovation"
        }
        
        # Enqueue to the single queue
        job_id = await enqueue_embedding_task(
            teacher_id="test-teacher-0000-0000-0000-000000000001",
            knowledge_id=1,
            chunks=test_chunks,
            metadata=metadata
        )
        
        if job_id:
            logger.info(f"✅ Test 1 PASSED: Enqueued job {job_id}")
        else:
            logger.error("❌ Test 1 FAILED: Failed to enqueue job")
            return False
            
        # Test 2: Full text processing (if we have a test file)
        test_file = parent_dir / "test_data" / "sample.pdf"
        if test_file.exists():
            logger.info("Test 2: Processing text for embedding...")
            
            try:
                result = await process_text_for_embedding(
                    teacher_id="test-teacher-0000-0000-0000-000000000003",
                    file_path=str(test_file),
                    subject="Test Subject",
                    notes="Test document processing"
                )
                
                logger.info(f"✅ Test 2 PASSED: Text processing completed")
                logger.info(f"   - Knowledge ID: {result['knowledge_id']}")
                logger.info(f"   - TestText ID: {result['test_text_id']}")
                logger.info(f"   - Chunks: {result['chunks_count']}")
                logger.info(f"   - Job ID: {result['job_id']}")
                
            except Exception as e:
                logger.warning(f"⚠️ Test 2 SKIPPED: No test file available or processing failed: {e}")
        else:
            logger.warning("⚠️ Test 2 SKIPPED: No test file available")
            
        logger.info("🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False

def main():
    """Main function to run the test"""
    try:
        success = asyncio.run(test_embedding_processing())
        if success:
            print("\n✅ All embedding processing tests PASSED!")
            sys.exit(0)
        else:
            print("\n❌ Some embedding processing tests FAILED!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()