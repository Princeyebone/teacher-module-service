#!/usr/bin/env python3
"""
Batch process curriculum files through the RAG pipeline and update KnowledgeMetadata table.

This script processes all PDF files in the curriculum folder, runs them through the 
RAG pipeline, and updates the corresponding KnowledgeMetadata records in the database.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Setup logging to match test_rag_pipeline.py style
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Progress tracking files
PROGRESS_FILE = "rag_processing_progress.txt"
FAILURE_FILE = "rag_processing_failures.txt"

# Import our modules
try:
    from database import get_db, async_engine
    from model import KnowledgeMetadata, KnowledgeEmbedding
    from rag.pipeline import process_document
    from sqlmodel import select
    logger.info("✅ All modules imported successfully")
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    sys.exit(1)

def log_progress(message: str, is_failure: bool = False):
    """Log progress to file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}\n"
    
    # Write to progress file
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(log_message)
    
    # Write to failure file if it's a failure
    if is_failure:
        with open(FAILURE_FILE, "a", encoding="utf-8") as f:
            f.write(log_message)

async def get_all_knowledge_metadata_by_filename(filename: str) -> List[KnowledgeMetadata]:
    """
    Find all KnowledgeMetadata records by pillar and filename.
    Creates its own database session to avoid connection issues.
    
    Args:
        filename: Filename to search for (without extension)
        
    Returns:
        List of KnowledgeMetadata records
    """
    logger.info(f"🔍 Searching for all KnowledgeMetadata records with syllabus pillar and filename: {filename}")
    
    # Remove extension from filename for comparison
    filename_without_ext = Path(filename).stem
    
    # Create a new database session for this operation
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        # Create multiple search patterns to handle different formatting variations
        # This handles cases like "Co-Intelligence_Living" vs "Co-Intelligence _ Living"
        search_patterns = [
            filename_without_ext,  # Exact match
            filename_without_ext.replace('_', ' '),  # Underscores to spaces
            filename_without_ext.replace(' ', '_'),  # Spaces to underscores
            filename_without_ext.replace('_', ' _ '),  # Handle "_ " pattern
            filename_without_ext.replace(' _ ', '_'),  # Handle " _" pattern
        ]
        
        # Remove duplicates and empty strings
        search_patterns = list(set(filter(None, search_patterns)))
        
        logger.info(f"   Search patterns: {search_patterns}")
        
        # Build conditions for all patterns
        conditions = []
        params = {}
        
        for i, pattern in enumerate(search_patterns):
            param_name_notes = f"search_notes_{i}"
            param_name_path = f"search_path_{i}"
            params[param_name_notes] = f"%{pattern}%"
            params[param_name_path] = f"%{pattern}%"
            
            conditions.append(f"LOWER(notes) LIKE LOWER(:{param_name_notes})")
            conditions.append(f"LOWER(file_path) LIKE LOWER(:{param_name_path})")
        
        # Combine all conditions
        all_conditions = " OR ".join(conditions)
        
        # Query for records where pillar contains 'syllabus' (case-insensitive) and 
        # either notes or file_path contains any of our filename variations (case-insensitive)
        from sqlalchemy import text
        stmt = select(KnowledgeMetadata).where(
            text(f"LOWER(pillar) LIKE '%syllabus%' AND ({all_conditions})")
        )
        
        result = await db.execute(stmt, params)
        records = result.scalars().all()
        
        logger.info(f"✅ Found {len(records)} KnowledgeMetadata record(s) for syllabus pillar and filename variations")
        for record in records:
            logger.info(f"   ID: {record.id}, Pillar: '{record.pillar}', File path: {record.file_path}, Notes: {record.notes}")
        
        return list(records)
    except Exception as e:
        logger.error(f"❌ Database query error: {e}")
        return []
    finally:
        await db_gen.aclose()

async def remove_duplicate_knowledge_metadata(records: List[KnowledgeMetadata]) -> Optional[KnowledgeMetadata]:
    """
    Remove duplicate KnowledgeMetadata records with same pillar and notes.
    Creates its own database session to avoid connection issues.
    
    Args:
        records: List of KnowledgeMetadata records
        
    Returns:
        The remaining KnowledgeMetadata record or None
    """
    if len(records) <= 1:
        return records[0] if records else None
    
    logger.info(f"🗑️  Found {len(records)} duplicate records, removing duplicates...")
    
    # Prefer record with .pdf extension
    pdf_record = None
    for record in records:
        if record.file_path and record.file_path.endswith('.pdf'):
            pdf_record = record
            break
    
    # If no .pdf record found, use the first one
    keep_record = pdf_record if pdf_record else records[0]
    
    # Create a new database session for this operation
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        # Remove all other records (need to handle foreign key constraints)
        for record in records:
            if record.id != keep_record.id:
                logger.info(f"🗑️  Removing duplicate record ID: {record.id}")
                try:
                    # First delete associated embeddings using raw SQL
                    from sqlalchemy import text
                    delete_stmt = text("DELETE FROM knowledgeembedding WHERE knowledge_id = :knowledge_id")
                    await db.execute(delete_stmt, {"knowledge_id": record.id})
                    await db.commit()
                    
                    logger.info(f"✅ Successfully removed embeddings for record ID: {record.id}")
                except Exception as e:
                    logger.error(f"❌ Error deleting embeddings for record {record.id}: {e}")
                    await db.rollback()
        
        logger.info(f"✅ Kept record ID: {keep_record.id} with file path: {keep_record.file_path}")
        return keep_record
    except Exception as e:
        logger.error(f"❌ Error removing duplicates: {e}")
        await db.rollback()
        return None
    finally:
        await db_gen.aclose()

async def update_knowledge_metadata_file_path(knowledge_id: int, new_file_path: str) -> bool:
    """
    Update the file_path of a KnowledgeMetadata record to use .pdf extension.
    Creates its own database session to avoid connection issues.
    
    Args:
        knowledge_id: ID of the KnowledgeMetadata record
        new_file_path: New file path with .pdf extension
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"🔄 Updating KnowledgeMetadata ID {knowledge_id} file_path to: {new_file_path}")
    
    # Create a new database session for this operation
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        stmt = select(KnowledgeMetadata).where(KnowledgeMetadata.id == knowledge_id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        
        if record:
            record.file_path = new_file_path
            db.add(record)
            await db.commit()
            logger.info(f"✅ Successfully updated file_path for KnowledgeMetadata ID {knowledge_id}")
            return True
        else:
            logger.error(f"❌ KnowledgeMetadata record not found for ID {knowledge_id}")
            await db.rollback()
            return False
    except Exception as e:
        logger.error(f"❌ Error updating file_path: {e}")
        await db.rollback()
        return False
    finally:
        await db_gen.aclose()

async def update_knowledge_metadata_after_processing(
    knowledge_id: int, 
    chunk_count: int,
    embedding_model: str = "gemini-embedding-001"
) -> bool:
    """
    Update KnowledgeMetadata record after successful processing.
    Creates its own database session to avoid connection issues.
    
    Args:
        knowledge_id: ID of the KnowledgeMetadata record
        chunk_count: Number of chunks processed
        embedding_model: Embedding model used
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"💾 Updating KnowledgeMetadata ID {knowledge_id} with processing results")
    
    # Create a new database session for this operation
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        stmt = select(KnowledgeMetadata).where(KnowledgeMetadata.id == knowledge_id)
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        
        if record:
            record.is_embedded = True
            record.chunk_count = chunk_count
            record.embedding_model = embedding_model
            record.last_indexed_at = datetime.utcnow()
            db.add(record)
            await db.commit()
            logger.info(f"✅ Successfully updated KnowledgeMetadata ID {knowledge_id}")
            return True
        else:
            logger.error(f"❌ KnowledgeMetadata record not found for ID {knowledge_id}")
            await db.rollback()
            return False
    except Exception as e:
        logger.error(f"❌ Error updating KnowledgeMetadata: {e}")
        await db.rollback()
        return False
    finally:
        await db_gen.aclose()

async def process_single_file(file_path: str) -> bool:
    """
    Process a single file through the RAG pipeline.
    
    Args:
        file_path: Path to the PDF file to process
        
    Returns:
        True if successful, False otherwise
    """
    filename = os.path.basename(file_path)
    logger.info(f"🚀 Starting processing for file: {filename}")
    
    # Check if file actually exists
    if not os.path.exists(file_path):
        error_msg = f"❌ File does not exist: {file_path}"
        logger.error(error_msg)
        log_progress(f"SKIPPED: {filename} - {error_msg}")
        return False
    
    try:
        # Find all matching KnowledgeMetadata records
        knowledge_records = await get_all_knowledge_metadata_by_filename(filename)
        if not knowledge_records:
            error_msg = f"❌ No KnowledgeMetadata record found for file: {filename}"
            logger.error(error_msg)
            log_progress(f"FAILED: {filename} - {error_msg}", is_failure=True)
            return False
            
        # Remove duplicates and ensure .pdf extension
        knowledge_record = await remove_duplicate_knowledge_metadata(knowledge_records)
        if not knowledge_record:
            error_msg = f"❌ No valid KnowledgeMetadata record after deduplication for file: {filename}"
            logger.error(error_msg)
            log_progress(f"FAILED: {filename} - {error_msg}", is_failure=True)
            return False
            
        # Ensure we have a valid ID
        if knowledge_record.id is None:
            error_msg = f"❌ KnowledgeMetadata record has no ID for file: {filename}"
            logger.error(error_msg)
            log_progress(f"FAILED: {filename} - {error_msg}", is_failure=True)
            return False
            
        knowledge_id = int(knowledge_record.id)
        
        # Update file_path to use .pdf extension if needed
        current_file_path = knowledge_record.file_path or ""
        if not current_file_path.endswith('.pdf'):
            # Change extension to .pdf
            path_obj = Path(current_file_path)
            new_file_path = str(path_obj.with_suffix('.pdf'))
            if not await update_knowledge_metadata_file_path(knowledge_id, new_file_path):
                error_msg = f"❌ Failed to update file_path for KnowledgeMetadata ID {knowledge_id}"
                logger.error(error_msg)
                log_progress(f"FAILED: {filename} - {error_msg}", is_failure=True)
                return False
            logger.info(f"🔄 Updated file path from {current_file_path} to {new_file_path}")
        
        # Process document through RAG pipeline
        logger.info(f"🧠 Running RAG pipeline for {filename}")
        result = await process_document(
            file_path=file_path,
            subject=knowledge_record.subject or "Unknown",
            notes=knowledge_record.notes or "",
            store_in_db=True  # Store results in database
        )
        
        logger.info(f"✅ RAG pipeline completed for {filename}")
        logger.info(f"   Chunks generated: {result['chunks_count']}")
        logger.info(f"   Successful embeddings: {result['embeddings_count']}")
        logger.info(f"   Stored in database: {result['stored_in_db']}")
        logger.info(f"   Knowledge ID: {result['knowledge_id']}")
        
        # Update KnowledgeMetadata with processing results
        if not await update_knowledge_metadata_after_processing(
            knowledge_id, 
            result['chunks_count']
        ):
            error_msg = f"❌ Failed to update KnowledgeMetadata after processing for ID {knowledge_id}"
            logger.error(error_msg)
            log_progress(f"FAILED: {filename} - {error_msg}", is_failure=True)
            return False
        
        logger.info(f"🎉 Successfully processed {filename}")
        log_progress(f"SUCCESS: {filename} - Chunks: {result['chunks_count']}, Embeddings: {result['embeddings_count']}")
        return True
        
    except Exception as e:
        error_msg = f"❌ Error processing file {filename}: {str(e)}"
        logger.error(error_msg)
        log_progress(f"FAILED: {filename} - {error_msg}", is_failure=True)
        return False

async def process_all_ragfiles() -> None:
    """
    Process all PDF files in the curriculum folder.
    """
    ragfiles_dir = Path("curriculum")
    
    if not ragfiles_dir.exists():
        error_msg = f"❌ curriculum directory not found: {ragfiles_dir.absolute()}"
        logger.error(error_msg)
        log_progress(f"FAILED: {error_msg}", is_failure=True)
        return
    
    # Get all PDF files
    pdf_files = list(ragfiles_dir.glob("*.pdf"))
    logger.info(f"📁 Found {len(pdf_files)} PDF files in curriculum directory")
    log_progress(f"STARTED: Found {len(pdf_files)} PDF files in curriculum directory")
    
    if not pdf_files:
        warning_msg = "⚠️  No PDF files found in curriculum directory"
        logger.warning(warning_msg)
        log_progress(f"WARNING: {warning_msg}")
        return
    
    # Process each file
    successful_count = 0
    failed_count = 0
    
    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"📄 Processing file {i}/{len(pdf_files)}: {pdf_file.name}")
        logger.info(f"{'='*80}")
        
        try:
            success = await process_single_file(str(pdf_file))
            if success:
                successful_count += 1
                logger.info(f"✅ Completed processing {pdf_file.name}")
            else:
                failed_count += 1
                logger.error(f"❌ Failed processing {pdf_file.name}")
                
        except Exception as e:
            failed_count += 1
            error_msg = f"💥 Unexpected error processing {pdf_file.name}: {str(e)}"
            logger.error(error_msg)
            log_progress(f"FAILED: {pdf_file.name} - {error_msg}", is_failure=True)
        
        # Add a small delay between files to avoid overwhelming the system
        if i < len(pdf_files):
            await asyncio.sleep(2)  # Increased delay to 2 seconds
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("📊 BATCH PROCESSING SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total files: {len(pdf_files)}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Success rate: {successful_count/len(pdf_files)*100:.1f}%" if pdf_files else "N/A")
    
    summary_msg = f"SUMMARY: Total={len(pdf_files)}, Success={successful_count}, Failed={failed_count}, Rate={successful_count/len(pdf_files)*100:.1f}%"
    log_progress(summary_msg)

if __name__ == "__main__":
    logger.info("🚀 Starting curriculum batch processing")
    log_progress("STARTED: curriculum batch processing initiated")
    
    try:
        asyncio.run(process_all_ragfiles())
        logger.info("🏁 curriculum batch processing completed")
        log_progress("COMPLETED: curriculum batch processing finished")
    except KeyboardInterrupt:
        logger.info("🛑 curriculum batch processing interrupted by user")
        log_progress("INTERRUPTED: curriculum batch processing interrupted by user")
    except Exception as e:
        logger.error(f"💥 curriculum batch processing failed: {str(e)}")
        log_progress(f"FAILED: curriculum batch processing failed: {str(e)}", is_failure=True)
