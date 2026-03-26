"""
Main Module for Embedding Generation Background Processing

This module provides the main interface for embedding generation background processing,
using the exact implementation from batch2_rag.py.

Usage:
    from app.rag_back.embedding_back import process_text_for_embedding
    
    # Process text and generate embeddings
    result = await process_text_for_embedding(
        teacher_id="teacher-uuid",
        file_path="/path/to/document.pdf",
        subject="Mathematics",
        notes="Algebra basics"
    )
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from uuid import UUID

# Initialize logger
logger = logging.getLogger(__name__)

# Import necessary modules
try:
    from .enqueue_embedding import enqueue_embedding_sync
except ImportError:
    # If running as script directly, add parent directory to path
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    from app.rag_back.enqueue_embedding import enqueue_embedding_sync

# Import text extraction and chunking functions from rag.text
try:
    from app.rag.text import extract_text_from_pdf_pymupdf, chunk_text_with_langchain
except ImportError as e:
    logger.error(f"Failed to import text processing functions: {e}")
    raise

# Import database functions
try:
    from app.core.database import get_db
    from app.models.model import KnowledgeMetadata, TestText
    from sqlalchemy import select
except ImportError as e:
    logger.error(f"Failed to import database functions: {e}")
    raise

async def process_text_for_embedding(
    teacher_id: str,
    file_path: str,
    subject: str = "Unknown",
    notes: str = "",
    level: str = "all levels",
    region: str = "all regions",
    pillar: str = "cognitive science and pedagogy",
    source_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main function to process text for embedding generation.
    
    This function:
    1. Extracts text from the document using PyMuPDF
    2. Chunks the text using LangChain
    3. Stores the chunks in TestText table
    4. Creates KnowledgeMetadata record
    5. Enqueues embedding generation task
    
    Args:
        teacher_id: UUID string of the teacher
        file_path: Path to the document file
        subject: Subject of the document
        notes: Additional notes about the document
        level: Educational level
        region: Geographic region
        pillar: Knowledge pillar
        source_url: Source URL of the document
        
    Returns:
        Dictionary containing processing results
    """
    logger.info(f"🚀 Starting text processing for embedding generation")
    logger.info(f"📁 File: {file_path}")
    logger.info(f"👨‍🏫 Teacher ID: {teacher_id}")
    logger.info(f"📚 Subject: {subject}")
    
    try:
        # Validate teacher_id is a valid UUID string
        try:
            UUID(teacher_id)
        except ValueError:
            raise ValueError(f"Invalid teacher_id: {teacher_id}")
        
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Step 1: Extract text from PDF using PyMuPDF (exact function from rag.text)
        logger.info("📄 Extracting text from PDF using PyMuPDF...")
        extracted_text = await extract_text_from_pdf_pymupdf(file_path)
        logger.info(f"✅ Extracted {len(extracted_text)} characters")
        
        # Step 2: Chunk text using LangChain (exact function from rag.text)
        logger.info("🧩 Chunking text using LangChain...")
        chunks = await chunk_text_with_langchain(extracted_text)
        logger.info(f"✅ Generated {len(chunks)} chunks")
        
        # Step 3: Store chunks in TestText table
        logger.info("💾 Storing chunks in TestText table...")
        
        # Get database session
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Create TestText record
            test_text_record = TestText(
                text="\n\n========== CHUNK BREAK ==========\n\n".join(chunks),
                file_path=file_path,
                subject=subject,
                notes=notes
            )
            
            db.add(test_text_record)
            await db.commit()
            await db.refresh(test_text_record)
            
            logger.info(f"✅ Stored TestText record with ID: {test_text_record.id}")
            
            # Step 4: Create KnowledgeMetadata record
            logger.info("📚 Creating KnowledgeMetadata record...")
            
            # Use file name without extension as notes if notes is empty
            if not notes:
                notes = Path(file_path).stem
            
            knowledge_record = KnowledgeMetadata(
                teacher_id=teacher_id,
                uploader_type="teacher",
                subject=subject,
                level=level,
                region=region,
                pillar=pillar,
                file_path=file_path,
                source_url=source_url,
                license=None,
                is_embedded=False,
                embedding_model="gemini-embedding-001",
                chunk_count=0,
                last_indexed_at=None,
                notes=notes
            )
            
            db.add(knowledge_record)
            await db.commit()
            await db.refresh(knowledge_record)
            
            logger.info(f"✅ Created KnowledgeMetadata record with ID: {knowledge_record.id}")
            
        except Exception as db_error:
            logger.error(f"❌ Database error: {db_error}")
            await db.rollback()
            raise
        finally:
            await db_gen.aclose()
        
        # Step 5: Enqueue embedding generation task
        logger.info("📬 Enqueuing embedding generation task...")
        
        # Prepare metadata for embedding task
        metadata = {
            "subject": subject,
            "notes": notes,
            "level": level,
            "region": region,
            "pillar": pillar,
            "source_url": source_url
        }
        
        # Enqueue task using round-robin distribution
        job_id = enqueue_embedding_sync(
            teacher_id=teacher_id,
            knowledge_id=knowledge_record.id,
            chunks=chunks,
            metadata=metadata
        )
        
        if job_id:
            logger.info(f"✅ Embedding task enqueued successfully with job ID: {job_id}")
        else:
            logger.error("❌ Failed to enqueue embedding task")
            raise RuntimeError("Failed to enqueue embedding task")
        
        # Return success result
        result = {
            "status": "success",
            "file_path": file_path,
            "knowledge_id": knowledge_record.id,
            "test_text_id": test_text_record.id,
            "chunks_count": len(chunks),
            "characters_extracted": len(extracted_text),
            "job_id": job_id,
            "message": "Text processing completed successfully. Embedding generation task enqueued."
        }
        
        logger.info("🎉 Text processing for embedding generation completed successfully")
        return result
        
    except Exception as e:
        error_msg = f"Text processing for embedding generation failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # Raise the exception to be handled by the caller
        raise RuntimeError(error_msg)

# Convenience function for direct use
def process_text_for_embedding_sync(
    teacher_id: str,
    file_path: str,
    subject: str = "Unknown",
    notes: str = "",
    level: str = "all levels",
    region: str = "all regions",
    pillar: str = "cognitive science and pedagogy",
    source_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronous version of process_text_for_embedding.
    
    Args:
        teacher_id: UUID string of the teacher
        file_path: Path to the document file
        subject: Subject of the document
        notes: Additional notes about the document
        level: Educational level
        region: Geographic region
        pillar: Knowledge pillar
        source_url: Source URL of the document
        
    Returns:
        Dictionary containing processing results
    """
    try:
        return asyncio.run(process_text_for_embedding(
            teacher_id=teacher_id,
            file_path=file_path,
            subject=subject,
            notes=notes,
            level=level,
            region=region,
            pillar=pillar,
            source_url=source_url
        ))
    except Exception as e:
        logger.error(f"❌ Failed to process text for embedding (sync): {e}")
        raise

if __name__ == "__main__":
    # Example usage
    print("This module provides functions for processing text for embedding generation.")
    print("Import and use the functions in your application code.")