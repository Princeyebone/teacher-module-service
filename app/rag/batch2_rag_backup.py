#!/usr/bin/env python3
"""
Batch process curriculum files through the RAG pipeline using unstructured.io for extraction first,
with PyMuPDF as fallback for extraction.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Any, Dict
from datetime import datetime
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
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Progress tracking files
PROGRESS_FILE = "rag_processing_progress_v2.txt"
FAILURE_FILE = "rag_processing_failures_v2.txt"

# Import modules
try:
    from app.core.database import get_db
    from app.models.model import KnowledgeMetadata
    from sqlmodel import select
    # Import pipeline components we want to reuse
    from app.rag.pipeline import (
        extract_text_elements,  # unstructured.io extraction
        chunk_text_blocks, 
        generate_embeddings, 
        store_knowledge_metadata, 
        store_embeddings
    )
    # Import PyMuPDF extraction as fallback
    async def extract_text_elements_with_pymupdf_fallback(file_path: str) -> List[Dict[str, Any]]:
        """Wrapper for PyMuPDF extraction to match the same interface as unstructured.io"""
        logger.info(f"Falling back to PyMuPDF extraction for: {file_path}")
        text_blocks = []
        
        try:
            # Run CPU-bound PyMuPDF operations in a thread pool
            loop = asyncio.get_event_loop()
            text_blocks = await loop.run_in_executor(None, _extract_pymupdf_internal, file_path)
            
            logger.info(f"PyMuPDF extraction completed. Found {len(text_blocks)} blocks.")
            return text_blocks
        except Exception as e:
            logger.error(f"Error during PyMuPDF extraction: {e}")
            raise
    
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

async def extract_text_elements_enhanced(file_path: str) -> List[Dict[str, Any]]:
    """
    Enhanced text extraction that first tries unstructured.io, then falls back to PyMuPDF.
    Returns list of text blocks compatible with the pipeline.
    """
    logger.info(f"Starting enhanced text extraction for: {file_path}")
    
    # First try unstructured.io
    try:
        logger.info("Attempting extraction with unstructured.io...")
        text_blocks = await extract_text_elements(file_path)
        logger.info(f"Unstructured.io extraction successful. Found {len(text_blocks)} blocks.")
        
        # If we got text blocks, filter and return them
        if text_blocks:
            filtered_blocks = _filter_text_blocks(text_blocks)
            logger.info(f"Filtered text blocks: {len(filtered_blocks)} (reduced from {len(text_blocks)})")
            return filtered_blocks
        else:
            logger.warning("Unstructured.io extraction returned 0 blocks. Falling back to PyMuPDF...")
            
    except Exception as e:
        logger.warning(f"Unstructured.io extraction failed: {e}. Falling back to PyMuPDF...")
    
    # Fallback to PyMuPDF
    try:
        text_blocks = await extract_text_elements_with_pymupdf_fallback(file_path)
        # Filter PyMuPDF blocks as well
        filtered_blocks = _filter_text_blocks(text_blocks)
        logger.info(f"Filtered PyMuPDF text blocks: {len(filtered_blocks)} (reduced from {len(text_blocks)})")
        return filtered_blocks
    except Exception as e:
        logger.error(f"PyMuPDF extraction also failed: {e}")
        raise

def _filter_text_blocks(text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter and deduplicate text blocks to remove excessive or repetitive content.
    
    Args:
        text_blocks: List of text blocks to filter
        
    Returns:
        Filtered list of text blocks
    """
    if not text_blocks:
        return text_blocks
    
    logger.info(f"Starting filtering of {len(text_blocks)} text blocks")
    
    # Step 1: Remove exact duplicates
    unique_blocks = []
    seen_texts = set()
    for block in text_blocks:
        text = block.get("text", "").strip()
        if text and text not in seen_texts:
            unique_blocks.append(block)
            seen_texts.add(text)
    
    logger.info(f"After deduplication: {len(unique_blocks)} blocks")
    
    # Step 2: Remove very short blocks (< 5 characters)
    filtered_blocks = [block for block in unique_blocks if len(block.get("text", "")) >= 5]
    logger.info(f"After removing very short blocks: {len(filtered_blocks)} blocks")
    
    # Step 3: Remove blocks with excessive repetition (e.g., same word repeated many times)
    final_blocks = []
    for block in filtered_blocks:
        text = block.get("text", "").strip()
        words = text.split()
        
        # Skip if text is mostly the same word repeated
        if words:
            unique_words = set(words)
            repetition_ratio = len(words) / len(unique_words) if unique_words else 0
            if repetition_ratio <= 10:  # Allow up to 10x repetition
                final_blocks.append(block)
            else:
                logger.debug(f"Skipping highly repetitive block: {text[:50]}...")
        else:
            final_blocks.append(block)
    
    logger.info(f"After removing repetitive blocks: {len(final_blocks)} blocks")
    
    # Log if we're still seeing excessive blocks
    if len(final_blocks) > 10000:
        logger.warning(f"Still have {len(final_blocks)} text blocks after filtering - this may indicate document structure issues")
        # Take only first 10000 blocks to prevent memory issues
        final_blocks = final_blocks[:10000]
        logger.info(f"Truncated to 10000 blocks to prevent memory issues")
    
    return final_blocks

def _extract_pymupdf_internal(file_path: str) -> List[Dict[str, Any]]:
    """Internal synchronous function for PyMuPDF extraction with OCR fallback"""
    text_blocks = []
    try:
        doc = fitz.open(file_path)
        logger.info(f"Processing PDF with {len(doc)} pages")
        
        # Keep track of page numbers and text content for better filtering
        page_data = []
        
        for page_num, page in enumerate(doc):
            # Track text content for this page to decide if OCR is needed
            page_text_content = ""
            page_blocks = []
            
            # Get text blocks
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" in block:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text:
                                page_text_content += text
                                # Simple heuristic for type based on font size
                                block_type = "NarrativeText"
                                if span["size"] > 14:  # Arbitrary threshold for headers
                                    block_type = "Title"
                                elif span["size"] < 9:
                                    block_type = "Footnote"
                                
                                page_blocks.append({
                                    "text": text,
                                    "type": block_type,
                                    "metadata": {
                                        "page_number": page_num + 1,
                                        "font": span["font"],
                                        "size": span["size"]
                                    }
                                })
            
            page_data.append({
                "page_num": page_num,
                "text_content": page_text_content,
                "blocks": page_blocks
            })
            
            # Check if page has very little text (likely scanned image)
            # Threshold: less than 50 characters for a whole page
            if len(page_text_content) < 50 and OCR_AVAILABLE:
                logger.info(f"Page {page_num + 1} has low text content ({len(page_text_content)} chars). Attempting OCR...")
                try:
                    # Render page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # 2x zoom for better OCR
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Perform OCR with timeout to prevent hanging
                    try:
                        ocr_text = pytesseract.image_to_string(img, timeout=30)  # 30 second timeout
                    except Exception as timeout_e:
                        logger.warning(f"OCR timed out for page {page_num + 1}: {timeout_e}")
                        ocr_text = ""  # Treat timeout as no text extracted
                        
                    if ocr_text.strip():
                        logger.info(f"OCR successful for page {page_num + 1}. Extracted {len(ocr_text)} chars.")
                        # Add as a single block since we lose layout info with simple OCR
                        text_blocks.append({
                            "text": ocr_text.strip(),
                            "type": "NarrativeText", # Default to narrative
                            "metadata": {
                                "page_number": page_num + 1,
                                "source": "OCR"
                            }
                        })
                    else:
                        logger.warning(f"OCR yielded no text for page {page_num + 1}")
                        # If OCR failed but we had some original text, keep it
                        if page_blocks:
                            text_blocks.extend(page_blocks)
                except Exception as ocr_e:
                    logger.error(f"OCR failed for page {page_num + 1}: {ocr_e}")
                    # Fallback to whatever we extracted originally
                    if page_blocks:
                        text_blocks.extend(page_blocks)
            else:
                # Sufficient text found, use extracted blocks
                text_blocks.extend(page_blocks)
        
        doc.close()
        
        # Apply additional filtering to remove repetitive content across pages
        filtered_blocks = _filter_pymupdf_blocks(text_blocks, page_data)
        logger.info(f"PyMuPDF extraction completed. Found {len(text_blocks)} blocks, filtered to {len(filtered_blocks)} blocks.")
        return filtered_blocks
    except Exception as e:
        logger.error(f"Internal PyMuPDF error: {e}")
        raise

def _filter_pymupdf_blocks(text_blocks: List[Dict[str, Any]], page_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Additional filtering for PyMuPDF blocks to remove repetitive content like headers/footers.
    
    Args:
        text_blocks: List of text blocks from PyMuPDF
        page_data: List of page-level data for analysis
        
    Returns:
        Filtered list of text blocks
    """
    if not text_blocks:
        return text_blocks
    
    # Identify potential headers/footers by checking if text appears on many pages
    text_frequency = {}
    for block in text_blocks:
        text = block.get("text", "").strip()
        if len(text) > 5 and len(text) < 100:  # Reasonable size for headers/footers
            text_frequency[text] = text_frequency.get(text, 0) + 1
    
    # Text that appears on more than 30% of pages is likely a header/footer
    total_pages = len(page_data)
    header_footer_threshold = max(3, total_pages * 0.3)  # At least 3 pages
    headers_footers = {text for text, count in text_frequency.items() if count > header_footer_threshold}
    
    if headers_footers:
        logger.info(f"Identified {len(headers_footers)} potential headers/footers: {list(headers_footers)[:5]}...")
    
    # Filter out headers/footers
    filtered_blocks = []
    for block in text_blocks:
        text = block.get("text", "").strip()
        if text not in headers_footers:
            filtered_blocks.append(block)
        else:
            logger.debug(f"Filtered out header/footer: {text[:50]}...")
    
    return filtered_blocks

async def process_document_enhanced(
    file_path: str, 
    subject: str = "Unknown",
    notes: str = "",
    max_tokens: int = 800,
    store_in_db: bool = True
) -> Dict[str, Any]:
    """
    Complete async pipeline that extracts text from a document using enhanced extraction 
    (unstructured.io first, PyMuPDF fallback), chunks it, generates embeddings, 
    and optionally stores results in the database.
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            logger.info(f"Starting document processing pipeline (Enhanced Extraction) for: {file_path} (Attempt {retry_count + 1})")
            
            # Step 1: Extract text elements using enhanced extraction
            text_blocks = await extract_text_elements_enhanced(file_path)
            logger.info(f"Extracted {len(text_blocks)} text blocks from document")
            
            # Step 2: Chunk text blocks (reusing existing chunking logic)
            chunks = await chunk_text_blocks(text_blocks, max_tokens)
            logger.info(f"Generated {len(chunks)} chunks from text blocks")
            
            # Apply additional deduplication to handle edge cases
            chunks = _deduplicate_chunks(chunks)
            logger.info(f"After aggressive deduplication: {len(chunks)} chunks")
            
            # Log chunk statistics
            if chunks:
                chunk_lengths = [len(chunk.split()) for chunk in chunks]  # Word count
                logger.info(f"Chunk word count statistics - Min: {min(chunk_lengths)}, Max: {max(chunk_lengths)}, Avg: {sum(chunk_lengths) // len(chunk_lengths)}")
            
            # Check for duplicates
            unique_chunks = list(set(chunks))
            if len(unique_chunks) != len(chunks):
                logger.warning(f"⚠️ Duplicate chunks detected: {len(chunks) - len(unique_chunks)} duplicates found. Deduplicating...")
                chunks = unique_chunks
                logger.info(f"Deduplicated chunk count: {len(chunks)}")
            
            # Step 3: Generate embeddings
            logger.info(f"Starting embedding generation for {len(chunks)} chunks")
            embeddings = await generate_embeddings(chunks)
            
            result = {
                "file_path": file_path,
                "subject": subject,
                "chunks_count": len(chunks),
                "embeddings_count": len([e for e in embeddings if e is not None]),
                "chunks": chunks,
                "embeddings": embeddings
            }
            
            # Step 4: Store in database if requested
            if store_in_db:
                # Database storage with retry logic
                db_max_retries = 3
                db_retry_count = 0
                
                while db_retry_count < db_max_retries:
                    try:
                        # Get database session
                        db_gen = get_db()
                        db = await db_gen.__anext__()
                        
                        try:
                            # Store knowledge metadata
                            knowledge_id = await store_knowledge_metadata(db, file_path, subject, notes)
                            result["knowledge_id"] = knowledge_id
                            
                            # Store embeddings
                            await store_embeddings(db, knowledge_id, chunks, embeddings)
                            
                            result["stored_in_db"] = True
                            break  # Success, break out of database retry loop
                        finally:
                            await db_gen.aclose()
                            
                    except Exception as db_error:
                        db_retry_count += 1
                        logger.warning(f"Database error during storage (Attempt {db_retry_count}/{db_max_retries}): {str(db_error)}")
                        
                        if db_retry_count >= db_max_retries:
                            logger.error(f"Failed to store in database after {db_max_retries} attempts")
                            raise db_error
                        else:
                            await asyncio.sleep(2 ** db_retry_count)
            
            else:
                result["stored_in_db"] = False
            
            logger.info(f"Document processing pipeline completed successfully.")
            return result
            
        except Exception as e:
            retry_count += 1
            logger.error(f"Error during document processing pipeline (Attempt {retry_count}): {str(e)}")
            
            if retry_count >= max_retries:
                raise
            
            wait_time = 2 ** retry_count
            logger.info(f"Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    raise RuntimeError("Document processing failed after all retries")

async def get_all_knowledge_metadata_by_filename(filename: str) -> List[KnowledgeMetadata]:
    """Find all KnowledgeMetadata records by pillar and filename."""
    logger.info(f"🔍 Searching for all KnowledgeMetadata records with syllabus pillar and filename: {filename}")
    
    filename_without_ext = Path(filename).stem
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        search_patterns = [
            filename_without_ext,
            filename_without_ext.replace('_', ' '),
            filename_without_ext.replace(' ', '_'),
            filename_without_ext.replace('_', ' _ '),
            filename_without_ext.replace(' _ ', '_'),
        ]
        search_patterns = list(set(filter(None, search_patterns)))
        
        conditions = []
        params = {}
        
        for i, pattern in enumerate(search_patterns):
            param_name_notes = f"search_notes_{i}"
            param_name_path = f"search_path_{i}"
            params[param_name_notes] = f"%{pattern}%"
            params[param_name_path] = f"%{pattern}%"
            
            conditions.append(f"LOWER(notes) LIKE LOWER(:{param_name_notes})")
            conditions.append(f"LOWER(file_path) LIKE LOWER(:{param_name_path})")
        
        all_conditions = " OR ".join(conditions)
        
        from sqlalchemy import text
        stmt = select(KnowledgeMetadata).where(
            text(f"LOWER(pillar) ILIKE '%evaluation%' AND ({all_conditions})")
        )
        
        result = await db.execute(stmt, params)
        records = result.scalars().all()
        return list(records)
    except Exception as e:
        logger.error(f"❌ Database query error: {e}")
        return []
    finally:
        await db_gen.aclose()

async def remove_duplicate_knowledge_metadata(records: List[KnowledgeMetadata]) -> Optional[KnowledgeMetadata]:
    """Remove duplicate KnowledgeMetadata records."""
    if len(records) <= 1:
        return records[0] if records else None
    
    logger.info(f"🗑️  Found {len(records)} duplicate records, removing duplicates...")
    
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
                logger.info(f"🗑️  Removing duplicate record ID: {record.id}")
                try:
                    from sqlalchemy import text
                    delete_stmt = text("DELETE FROM knowledgeembedding WHERE knowledge_id = :knowledge_id")
                    await db.execute(delete_stmt, {"knowledge_id": record.id})
                    await db.commit()
                except Exception as e:
                    logger.error(f"❌ Error deleting embeddings for record {record.id}: {e}")
                    await db.rollback()
        return keep_record
    except Exception as e:
        logger.error(f"❌ Error removing duplicates: {e}")
        await db.rollback()
        return None
    finally:
        await db_gen.aclose()

async def update_knowledge_metadata_file_path(knowledge_id: int, new_file_path: str) -> bool:
    """Update the file_path of a KnowledgeMetadata record."""
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
            return True
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
    """Update KnowledgeMetadata record after successful processing."""
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
        logger.error(f"❌ Error updating KnowledgeMetadata: {e}")
        await db.rollback()
        return False
    finally:
        await db_gen.aclose()

async def process_single_file(file_path: str) -> bool:
    """Process a single file through the enhanced RAG pipeline (unstructured.io first, PyMuPDF fallback)."""
    filename = os.path.basename(file_path)
    logger.info(f"🚀 Starting processing for file: {filename}")
    
    if not os.path.exists(file_path):
        error_msg = f"❌ File does not exist: {file_path}"
        logger.error(error_msg)
        log_progress(f"SKIPPED: {filename} - {error_msg}")
        return False
    
    try:
        knowledge_records = await get_all_knowledge_metadata_by_filename(filename)
        if not knowledge_records:
            error_msg = f"❌ No KnowledgeMetadata record found for file: {filename}"
            logger.error(error_msg)
            log_progress(f"FAILED: {filename} - {error_msg}", is_failure=True)
            return False
            
        knowledge_record = await remove_duplicate_knowledge_metadata(knowledge_records)
        if not knowledge_record:
            return False
            
        if knowledge_record.id is None:
            return False
            
        knowledge_id = int(knowledge_record.id)
        
        current_file_path = knowledge_record.file_path or ""
        if not current_file_path.endswith('.pdf'):
            path_obj = Path(current_file_path)
            new_file_path = str(path_obj.with_suffix('.pdf'))
            if not await update_knowledge_metadata_file_path(knowledge_id, new_file_path):
                return False
        
        logger.info(f"🧠 Running RAG pipeline (Enhanced Extraction) for {filename}")
        result = await process_document_enhanced(
            file_path=file_path,
            subject=knowledge_record.subject or "Unknown",
            notes=knowledge_record.notes or "",
            max_tokens=800,  # Explicitly set to 800 tokens
            store_in_db=True
        )
        
        if not await update_knowledge_metadata_after_processing(
            knowledge_id, 
            result['chunks_count']
        ):
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
    """Process all PDF files in the curriculum folder."""
    ragfiles_dir = Path("Evaluation")
    
    if not ragfiles_dir.exists():
        error_msg = f"❌ Evaluation directory not found: {ragfiles_dir.absolute()}"
        logger.error(error_msg)
        log_progress(f"FAILED: {error_msg}", is_failure=True)
        return
    
    pdf_files = list(ragfiles_dir.glob("*.pdf"))
    logger.info(f"📁 Found {len(pdf_files)} PDF files in Evaluation directory")
    log_progress(f"STARTED: Found {len(pdf_files)} PDF files in Evaluation directory")
    
    if not pdf_files:
        return
    
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
            else:
                failed_count += 1
                
        except Exception as e:
            failed_count += 1
            error_msg = f"💥 Unexpected error processing {pdf_file.name}: {str(e)}"
            logger.error(error_msg)
            log_progress(f"FAILED: {pdf_file.name} - {error_msg}", is_failure=True)
        
        if i < len(pdf_files):
            await asyncio.sleep(2)
    
    logger.info(f"\n{'='*80}")
    logger.info("📊 BATCH PROCESSING SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total files: {len(pdf_files)}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed: {failed_count}")
    
    summary_msg = f"SUMMARY: Total={len(pdf_files)}, Success={successful_count}, Failed={failed_count}"
    log_progress(summary_msg)

if __name__ == "__main__":
    logger.info("🚀 Starting curriculum batch processing (Enhanced Extraction)")
    log_progress("STARTED: curriculum batch processing initiated (Enhanced Extraction)")
    
    try:
        asyncio.run(process_all_ragfiles())
        logger.info("🏁 curriculum batch processing completed")
        log_progress("COMPLETED: curriculum batch processing finished")
    except KeyboardInterrupt:
        logger.info("🛑 curriculum batch processing interrupted by user")
    except Exception as e:
        logger.error(f"💥 curriculum batch processing failed: {str(e)}")

def _deduplicate_chunks(chunks: List[str]) -> List[str]:
    """
    Aggressive deduplication of chunks to handle edge cases.
    
    Args:
        chunks: List of text chunks
        
    Returns:
        Deduplicated list of chunks
    """
    if not chunks:
        return chunks
    
    # Remove exact duplicates
    unique_chunks = list(set(chunks))
    if len(unique_chunks) != len(chunks):
        logger.info(f"Removed {len(chunks) - len(unique_chunks)} exact duplicate chunks")
        chunks = unique_chunks
    
    # Remove near-duplicates (chunks that are substrings of others)
    filtered_chunks = []
    for i, chunk in enumerate(chunks):
        is_substring = False
        for j, other_chunk in enumerate(chunks):
            if i != j and chunk in other_chunk and len(chunk) < len(other_chunk) * 0.8:
                is_substring = True
                break
        if not is_substring:
            filtered_chunks.append(chunk)
    
    if len(filtered_chunks) != len(chunks):
        logger.info(f"Removed {len(chunks) - len(filtered_chunks)} substring chunks")
    
    return filtered_chunks
