#!/usr/bin/env python3
"""
Example script showing how to use the RAG pipeline with database storage
"""

import asyncio
import sys
import os

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.pipeline import process_document

async def example_document_processing():
    """Example of processing a document and storing results in the database"""
    print("Example: Processing a document with RAG pipeline and storing in database")
    
    # Create a sample document
    sample_document = """
    # Introduction to Machine Learning
    
    Machine learning is a subset of artificial intelligence that focuses on algorithms 
    and statistical models that enable computers to perform tasks without explicit 
    instructions.
    
    ## Key Concepts
    
    - **Supervised Learning**: Learning from labeled training data
    - **Unsupervised Learning**: Finding patterns in unlabeled data
    - **Reinforcement Learning**: Learning through interaction with an environment
    
    ## Applications
    
    Machine learning has numerous applications including:
    - Image recognition
    - Natural language processing
    - Recommendation systems
    - Autonomous vehicles
    
    The field continues to evolve rapidly with new techniques and applications 
    being developed regularly.
    """
    
    # Save to a file
    document_path = "ml_introduction.txt"
    with open(document_path, "w") as f:
        f.write(sample_document)
    
    try:
        # Process the document and store in database
        result = await process_document(
            file_path=document_path,
            subject="Computer Science",
            notes="Introduction to ML concepts",
            max_tokens=500,  # Smaller chunks for better granularity
            store_in_db=True  # Store results in database
        )
        
        print(f"✅ Document processed successfully!")
        print(f"   Knowledge ID: {result.get('knowledge_id', 'N/A')}")
        print(f"   Chunks generated: {result['chunks_count']}")
        print(f"   Embeddings stored: {result['embeddings_count']}")
        
        # Display some chunk information
        if result['chunks']:
            print(f"\n📝 First chunk preview:")
            first_chunk = result['chunks'][0]
            print(f"   Length: {len(first_chunk)} characters")
            print(f"   Content: {first_chunk[:100]}...")
            
        return True
        
    except Exception as e:
        print(f"❌ Document processing failed: {str(e)}")
        # Check if it's a quota error
        if "quota" in str(e).lower() or "429" in str(e):
            print("⚠️  This is likely a quota error. Consider:")
            print("   1. Waiting a few minutes before trying again")
            print("   2. Requesting a quota increase from Google Cloud")
            print("   3. Using the pipeline with store_in_db=False for testing")
        return False
    finally:
        # Clean up the sample file
        if os.path.exists(document_path):
            os.remove(document_path)

if __name__ == "__main__":
    print("Running RAG pipeline example...")
    result = asyncio.run(example_document_processing())
    if result:
        print("\n✅ Example completed successfully!")
    else:
        print("\n❌ Example failed!")
        sys.exit(1)