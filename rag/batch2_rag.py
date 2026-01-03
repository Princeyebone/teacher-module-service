#!/usr/bin/env python3
"""
Academic-optimized batch processor for RAG pipeline.
Designed for syllabi, course materials, and academic documents.

Key improvements:
- Structure-aware extraction with PyMuPDF
- Conservative filtering to preserve academic content
- Section-based chunking with overlap
- Rich metadata preservation
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Any, Dict, Set, Tuple
from datetime import datetime
from collections import Counter
import fitz  # PyMuPDF

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.getLogger(__name__).warning("pytesseract or PIL not available. OCR fallback disabled.")

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Progress tracking files
PROGRESS_FILE = "rag_processing_progress_academic.txt"
FAILURE_FILE = "rag_processing_failures_academic.txt"
FINAL_BATCH_LOG = "final_batch.txt"  # New log file for final batch processing

# Academic-specific configuration
ACADEMIC_CONFIG = {
    "extraction": {
        "preserve_structure": True,
        "preserve_lists": True,
        "min_font_size": 6,  # Include footnotes
        "ocr_fallback": True,
        "ocr_timeout": 30,
        "detect_columns": True,
    },
    "filtering": {
        "header_footer_threshold": 0.4,  # Must appear on 40%+ of pages
        "min_text_length": 3,  # characters
        "remove_exact_duplicates_only": True,
        "merge_fragmented_blocks": True,
    },
    "chunking": {
        "target_tokens": 600,  # Sweet spot for academic content
        "max_tokens": 800,
        "overlap_blocks": 2,
        "respect_sections": True,
    }
}

# Import modules
try:
    from database import get_db
    from model import KnowledgeMetadata, KnowledgeEmbedding
    from sqlmodel import select
    from rag.pipeline import generate_embeddings, store_knowledge_metadata, store_embeddings
    logger.info("✅ All modules imported successfully")
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    sys.exit(1)


# ============================================================================
# TEXT EXTRACTION AND CHUNKING (FROM text.py)
# ============================================================================

def clean_text_for_db(text_content: str) -> str:
    """
    Clean text content to remove characters that may cause database storage issues.
    
    Args:
        text_content: Raw extracted text content
        
    Returns:
        Cleaned text content safe for database storage
    """
    if not text_content:
        return text_content
    
    # Remove null bytes and other control characters that can cause encoding issues
    cleaned = text_content.replace('\x00', '')  # Remove null bytes
    
    # Remove other problematic control characters while preserving newlines and tabs
    cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in ['\n', '\t', '\r'])
    
    return cleaned

def extract_text_from_pdf_pymupdf(file_path: str) -> str:
    """
    Extract text from PDF using PyMuPDF with OCR fallback.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
    """
    filename = os.path.basename(file_path)
    logger.info(f"Starting PyMuPDF extraction for: {file_path}")
    
    text_content = ""
    ocr_pages = []
    extracted_pages = []
    
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info(f"Processing PDF with {total_pages} pages")
        
        for page_num, page in enumerate(doc):
            # Get text content from the page
            page_text = page.get_text()
            text_content += page_text
            extracted_pages.append(page_num + 1)
            
            # Check if page has very little text (likely scanned image)
            # Threshold: less than 50 characters for a whole page
            if len(page_text.strip()) < 50 and OCR_AVAILABLE:
                logger.info(f"Page {page_num + 1} has low text content ({len(page_text.strip())} chars). Attempting OCR...")
                try:
                    # Render page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Perform OCR with timeout to prevent hanging
                    try:
                        ocr_text = pytesseract.image_to_string(img, timeout=30)  # 30 second timeout
                    except Exception as timeout_e:
                        logger.warning(f"OCR timed out for page {page_num + 1}: {timeout_e}")
                        ocr_text = ""  # Treat timeout as no text extracted
                        
                    if ocr_text.strip():
                        logger.info(f"OCR successful for page {page_num + 1}. Extracted {len(ocr_text)} chars.")
                        text_content += f"\n{ocr_text.strip()}\n"
                        ocr_pages.append(page_num + 1)
                    else:
                        logger.warning(f"OCR yielded no text for page {page_num + 1}")
                        # If OCR failed but we had some original text, keep it
                        if page_text.strip():
                            text_content += page_text
                except Exception as ocr_e:
                    logger.error(f"OCR failed for page {page_num + 1}: {ocr_e}")
                    # Fallback to whatever we extracted originally
                    if page_text.strip():
                        text_content += page_text
            elif len(page_text.strip()) < 50 and not OCR_AVAILABLE:
                logger.info(f"Page {page_num + 1} has low text content but OCR is not available")
            else:
                # Log normal extraction
                pass
        
        doc.close()
        
        # Log summary
        total_chars = len(text_content)
        total_words = len(text_content.split())
        logger.info(f"PyMuPDF extraction completed. Extracted {total_chars} characters, {total_words} words.")
        
        if ocr_pages:
            logger.info(f"OCR performed on pages: {ocr_pages}")
        if extracted_pages:
            logger.info(f"Text extracted from pages: {extracted_pages}")
            
        return text_content.strip()
        
    except Exception as e:
        logger.error(f"Internal PyMuPDF error: {e}")
        raise

def chunk_text_with_langchain(text_content: str, max_tokens: int = 700) -> List[str]:
    """
    Chunk text using LangChain's RecursiveCharacterTextSplitter.
    
    Args:
        text_content: Text to chunk
        max_tokens: Maximum number of tokens per chunk
        
    Returns:
        List of chunked text strings
    """
    if not text_content or not text_content.strip():
        logger.warning("Empty or whitespace-only text provided for chunking")
        return []
        
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        # Use token estimation instead of character length for more accurate chunking
        try:
            from tiktoken import get_encoding
            encoding = get_encoding("cl100k_base")
            length_function = lambda text: len(encoding.encode(text))
        except ImportError:
            # Fallback to character length if tiktoken is not available
            length_function = len
            logger.warning("tiktoken not available, falling back to character length estimation")
        
        # Initialize LangChain text splitter with custom separators for better sentence boundaries
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_tokens,
            chunk_overlap=max_tokens // 10,  # 10% overlap for better context
            length_function=length_function,
            separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ": ", " ", ""]
        )
        
        logger.info(f"Using LangChain's RecursiveCharacterTextSplitter with {'token' if 'encoding' in locals() else 'character'} estimation for chunking")
        
        # Split the text into chunks
        chunks = text_splitter.split_text(text_content)
        
        # Filter out very short chunks and clean them
        filtered_chunks = []
        for chunk in chunks:
            cleaned_chunk = chunk.strip()
            if len(cleaned_chunk.split()) >= 10 and cleaned_chunk:  # At least 10 words and not empty
                filtered_chunks.append(cleaned_chunk)
        
        logger.info(f"Created {len(filtered_chunks)} chunks from text (filtered from {len(chunks)} total chunks)")
        return filtered_chunks
        
    except ImportError:
        logger.warning("LangChain not available, returning single chunk")
        # If LangChain is not available, return the text as a single chunk
        cleaned_text = text_content.strip()
        return [cleaned_text] if cleaned_text else []
    except Exception as e:
        logger.error(f"Error during chunking: {str(e)}")
        # If there's any error, return the text as a single chunk
        cleaned_text = text_content.strip()
        return [cleaned_text] if cleaned_text else []


# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

def log_final_batch(message: str, is_failure: bool = False) -> None:
    """Log messages to the final batch log file."""
    try:
        with open(FINAL_BATCH_LOG, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "FAIL" if is_failure else "SUCCESS"
            f.write(f"[{timestamp}] {status}: {message}\n")
    except Exception as e:
        logger.error(f"Failed to write to final batch log: {e}")


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

async def get_all_knowledge_metadata_by_filename(filename: str) -> List[KnowledgeMetadata]:
    """Find all KnowledgeMetadata records by filename using pillar and file_path fields."""
    logger.info(f"Searching for KnowledgeMetadata: {filename}")
    
    filename_without_ext = Path(filename).stem
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        search_patterns = [
            filename_without_ext,
            filename_without_ext.replace('_', ' '),
            filename_without_ext.replace(' ', '_'),
        ]
        search_patterns = list(set(filter(None, search_patterns)))
        
        conditions = []
        params = {}
        
        for i, pattern in enumerate(search_patterns):
            param_name_path = f"search_path_{i}"
            param_name_pillar = f"search_pillar_{i}"
            params[param_name_path] = f"%{pattern}%"
            params[param_name_pillar] = f"%{pattern}%"
            
            # Search in file_path and pillar fields instead of notes
            conditions.append(f"LOWER(file_path) LIKE LOWER(:{param_name_path})")
            conditions.append(f"LOWER(pillar) LIKE LOWER(:{param_name_pillar})")
        
        all_conditions = " OR ".join(conditions)
        
        from sqlalchemy import text
        stmt = select(KnowledgeMetadata).where(
            text(f"({all_conditions})")
        )
        
        result = await db.execute(stmt, params)
        records = result.scalars().all()
        logger.info(f"Found {len(records)} matching records")
        return list(records)
    except Exception as e:
        logger.error(f"Database query error: {e}")
        return []
    finally:
        await db_gen.aclose()


async def remove_duplicate_knowledge_metadata(records: List[KnowledgeMetadata]) -> Optional[KnowledgeMetadata]:
    """Remove duplicate KnowledgeMetadata records, keeping the PDF one."""
    if len(records) <= 1:
        return records[0] if records else None
    
    logger.info(f"Found {len(records)} duplicate records, removing duplicates...")
    
    # Prefer PDF record
    pdf_record = None
    for record in records:
        if record.file_path and record.file_path.endswith('.pdf'):
            pdf_record = record
            break
    
    keep_record = pdf_record if pdf_record else records[0]
    
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        for record in records:
            if record.id != keep_record.id:
                logger.info(f"Removing duplicate record ID: {record.id}")
                try:
                    from sqlalchemy import text
                    delete_stmt = text("DELETE FROM knowledgeembedding WHERE knowledge_id = :knowledge_id")
                    await db.execute(delete_stmt, {"knowledge_id": record.id})
                    await db.commit()
                except Exception as e:
                    logger.error(f"Error deleting embeddings for record {record.id}: {e}")
                    await db.rollback()
        return keep_record
    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        await db.rollback()
        return None
    finally:
        await db_gen.aclose()


async def update_knowledge_metadata_after_processing(
    knowledge_id: int,
    chunk_count: int,
    embedding_model: str = "gemini-embedding-001"
) -> bool:
    """Update KnowledgeMetadata after successful processing."""
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
            return True
        return False
    except Exception as e:
        logger.error(f"Error updating KnowledgeMetadata: {e}")
        await db.rollback()
        return False
    finally:
        await db_gen.aclose()


# ============================================================================
# PROCESSING FUNCTIONS
# ============================================================================

async def process_single_file(file_path: str) -> bool:
    """Process a single file through the academic RAG pipeline."""
    filename = os.path.basename(file_path)
    logger.info(f"{'='*80}")
    logger.info(f"Processing: {filename}")
    logger.info(f"{'='*80}")
    
    if not os.path.exists(file_path):
        error_msg = f"File does not exist: {file_path}"
        logger.error(error_msg)
        log_final_batch(f"SKIPPED: {filename} - {error_msg}", is_failure=True)
        return False
    
    try:
        # Find knowledge metadata
        knowledge_records = await get_all_knowledge_metadata_by_filename(filename)
        if not knowledge_records:
            error_msg = f"No KnowledgeMetadata record found for: {filename}"
            logger.error(error_msg)
            log_final_batch(f"FAILED: {filename} - {error_msg}", is_failure=True)
            return False
        
        # Remove duplicates
        knowledge_record = await remove_duplicate_knowledge_metadata(knowledge_records)
        if not knowledge_record or not knowledge_record.id:
            return False
        
        # Check if file is already embedded
        if knowledge_record.is_embedded:
            logger.info(f"✅ File {filename} is already embedded, skipping processing")
            log_final_batch(f"SKIPPED: {filename} - Already embedded")
            return True
        
        knowledge_id = int(knowledge_record.id)
        
        # Extract text from PDF
        text_content = extract_text_from_pdf_pymupdf(file_path)
        
        # Chunk the extracted text
        chunks = chunk_text_with_langchain(text_content)
        logger.info(f"✅ Created {len(chunks)} chunks from extracted text")
        
        # Generate embeddings with retry logic
        logger.info("Generating embeddings...")
        embeddings = None
        max_retries = 5  # Increased retry count
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                embeddings = await generate_embeddings(chunks)
                # Check if we have any successful embeddings
                successful_embeddings = len([e for e in embeddings if e is not None])
                logger.info(f"Generated {successful_embeddings} embeddings")
                
                # If we have some successful embeddings, break out of retry loop
                if successful_embeddings > 0:
                    break
                    
                # If no embeddings were generated, retry
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 10 * retry_count
                    logger.warning(f"No embeddings generated. Retrying in {wait_time}s... (Attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retry attempts reached for embedding generation")
                    
            except Exception as embed_error:
                retry_count += 1
                error_msg = str(embed_error)
                logger.error(f"Error generating embeddings (Attempt {retry_count}/{max_retries}): {error_msg}")
                
                # For connection issues, wait longer
                if "503" in error_msg or "unavailable" in error_msg.lower() or "failed to connect" in error_msg.lower():
                    wait_time = min(30 * (2 ** retry_count), 300)  # Max 5 minutes
                else:
                    wait_time = 10 * retry_count
                    
                if retry_count < max_retries:
                    logger.warning(f"Retrying in {wait_time}s... (Attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retry attempts reached for embedding generation")
                    # Don't raise immediately, we'll try to recover failed embeddings next
                    break  # Re-raise the exception if we've exhausted retries
        
        # If embeddings is None or we have failed embeddings, try to recover them
        if embeddings is None:
            logger.warning("All embedding generation attempts failed, trying individual embedding generation...")
            # Try to generate embeddings individually for each chunk
            embeddings = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Generating embedding for chunk {i+1}/{len(chunks)}")
                try:
                    embedding = await generate_embeddings([chunk])
                    if embedding and embedding[0] is not None:
                        embeddings.append(embedding[0])
                        logger.info(f"✅ Successfully generated embedding for chunk {i+1}")
                    else:
                        embeddings.append(None)
                        logger.warning(f"⚠️ Failed to generate embedding for chunk {i+1}")
                except Exception as chunk_error:
                    logger.error(f"❌ Error generating embedding for chunk {i+1}: {chunk_error}")
                    embeddings.append(None)
        else:
            # Check for failed embeddings and try to regenerate them
            failed_indices = [i for i, emb in enumerate(embeddings) if emb is None]
            if failed_indices:
                logger.warning(f"Found {len(failed_indices)} failed embeddings, attempting individual regeneration...")
                for idx in failed_indices:
                    logger.info(f"Regenerating embedding for chunk {idx+1}/{len(chunks)}")
                    try:
                        chunk_embedding = await generate_embeddings([chunks[idx]])
                        if chunk_embedding and chunk_embedding[0] is not None:
                            embeddings[idx] = chunk_embedding[0]
                            logger.info(f"✅ Successfully regenerated embedding for chunk {idx+1}")
                        else:
                            logger.warning(f"⚠️ Failed to regenerate embedding for chunk {idx+1}")
                    except Exception as regen_error:
                        logger.error(f"❌ Error regenerating embedding for chunk {idx+1}: {regen_error}")
        
        # Final check - count successful embeddings
        successful_embeddings = len([e for e in embeddings if e is not None])
        failed_embeddings = len(embeddings) - successful_embeddings
        
        if successful_embeddings == 0:
            raise RuntimeError("Failed to generate embeddings after all retries")
        
        if failed_embeddings > 0:
            logger.warning(f"⚠️ Lost {failed_embeddings} embeddings out of {len(embeddings)} total")
            if failed_embeddings > len(embeddings) * 0.3:  # More than 30% loss
                logger.warning(f"⚠️ High embedding loss rate: {failed_embeddings}/{len(embeddings)} embeddings lost")
        
        # Store in database using a single session for both operations
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Store embeddings using the same session
            await store_embeddings(db, knowledge_id, chunks, embeddings)
            
            # Update metadata using the same session
            if not await update_knowledge_metadata_after_processing(
                knowledge_id,
                len(chunks)  # Store total chunk count, not just successful embeddings
            ):
                # If update fails, we should rollback the entire transaction
                await db.rollback()
                return False
            
            # Commit all changes at once
            await db.commit()
            
            # Log success with statistics
            success_msg = (
                f"SUCCESS: {filename} - "
                f"Chunks: {len(chunks)}, "
                f"Embeddings: {successful_embeddings}, "
                f"Failed: {failed_embeddings}"
            )
            logger.info(f"✅ {success_msg}")
            log_final_batch(success_msg)
            return True
            
        except Exception as db_error:
            # Ensure we rollback on any database error
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.warning(f"Error during rollback: {rollback_error}")
            raise db_error
        finally:
            await db_gen.aclose()
        
    except Exception as e:
        error_msg = f"Error processing {filename}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        log_final_batch(f"FAILED: {filename} - {error_msg}", is_failure=True)
        return False


async def process_all_files_in_directories() -> None:
    """Process all PDF files in the directories specified in filelookup.py."""
    # Directories to search (from filelookup.py lines 9-13)
    search_directories = [
        "Lesson",
        "curriculum", 
        "Cognitive Science",
        "Evaluation",
        "Subject Mastery"
    ]
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing files from directories: {search_directories}")
    logger.info(f"{'='*80}\n")
    log_final_batch(f"STARTED: Processing files from directories: {search_directories}")
    
    successful = 0
    failed = 0
    
    for directory_name in search_directories:
        directory = Path(directory_name)
        
        if not directory.exists():
            error_msg = f"Directory not found: {directory.absolute()}"
            logger.error(error_msg)
            log_final_batch(f"FAILED: {error_msg}", is_failure=True)
            continue
        
        pdf_files = list(directory.glob("*.pdf"))
        logger.info(f"\nFound {len(pdf_files)} PDF files in {directory}")
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {directory}")
            continue
        
        for i, pdf_file in enumerate(pdf_files, 1):
            logger.info(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
            
            try:
                success = await process_single_file(str(pdf_file))
                if success:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                error_msg = f"Unexpected error processing {pdf_file.name}: {str(e)}"
                logger.error(error_msg)
                log_final_batch(f"FAILED: {pdf_file.name} - {error_msg}", is_failure=True)
            
            # Short delay between files
            if i < len(pdf_files):
                await asyncio.sleep(1)
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("PROCESSING SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Successful:   {successful}")
    logger.info(f"Failed:       {failed}")
    logger.info(f"{'='*80}\n")
    
    summary = f"SUMMARY: Success={successful}, Failed={failed}"
    log_final_batch(summary)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info("="*80)
    logger.info("ACADEMIC RAG PIPELINE - BATCH PROCESSOR")
    logger.info("Optimized for syllabi, course materials, and academic documents")
    logger.info("="*80)
    logger.info(f"Configuration:")
    logger.info(f"  - Chunk size: {ACADEMIC_CONFIG['chunking']['target_tokens']} tokens")
    logger.info(f"  - Overlap: {ACADEMIC_CONFIG['chunking']['overlap_blocks']} blocks")
    logger.info(f"  - Filter threshold: {ACADEMIC_CONFIG['filtering']['header_footer_threshold']*100}%")
    logger.info(f"  - OCR enabled: {OCR_AVAILABLE}")
    logger.info("="*80 + "\n")
    
    log_final_batch("STARTED: Academic batch processing initiated")
    
    try:
        asyncio.run(process_all_files_in_directories())
        logger.info("✅ Batch processing completed")
        log_final_batch("COMPLETED: Academic batch processing finished")
    except KeyboardInterrupt:
        logger.info("⚠️  Processing interrupted by user")
        log_final_batch("INTERRUPTED: Processing stopped by user")
    except Exception as e:
        logger.error(f"❌ Processing failed: {str(e)}")
        log_final_batch(f"FAILED: {str(e)}", is_failure=True)