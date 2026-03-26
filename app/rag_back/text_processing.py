"""
Background Text Processing for RAG Back Operations

This module contains the text processing logic specifically for the RAG back operations.
It's separate from the main RAG text processing to ensure proper separation of concerns.
"""

import os
import sys
import logging
import traceback
from typing import List, Optional
from pathlib import Path
import asyncio
from uuid import UUID

# Add the parent directory to the path so we can import config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import configuration and utilities
try:
    from app.core.config import settings
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Import text sanitization function
try:
    from app.rag.text import sanitize_text_for_database
    SANITIZATION_AVAILABLE = True
except ImportError:
    SANITIZATION_AVAILABLE = False
    logger.warning("⚠️ Text sanitization function not available. Will use basic cleaning.")

logger = logging.getLogger(__name__)

# Try to import PyMuPDF for PDF text extraction
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    logger.info("✅ PyMuPDF (fitz) available for PDF text extraction")
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("⚠️ PyMuPDF (fitz) not available. PDF text extraction will be limited.")

# Try to import OCR libraries
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
    logger.info("✅ OCR libraries (pytesseract, PIL) available for PDF text extraction")
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("⚠️ OCR libraries not available. OCR fallback will be disabled.")

# Try to import LangChain for advanced chunking
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
    logger.info("✅ LangChain available for advanced text chunking")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("⚠️ LangChain not available. Will use basic chunking.")

# Try to import tiktoken for accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    logger.info("✅ tiktoken available for accurate token estimation")
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("⚠️ tiktoken not available. Falling back to character length estimation.")

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

async def store_chunks_in_testtext_table(book_name: str, chunks: List[str]) -> Optional[int]:
    """
    Store chunks in the TestText database table as concatenated text with separators.
    
    Args:
        book_name: Name of the book/PDF file
        chunks: List of chunked text strings
        
    Returns:
        ID of the created TestText record if successful, None if failed
    """
    logger.info(f"Storing {len(chunks)} chunks for '{book_name}' in TestText table")
    
    if not chunks:
        logger.warning(f"No chunks to store for '{book_name}'")
        chunks = ["No content extracted from this document."]
    
    # Join chunks with clear separators for easy viewing
    # Each chunk is separated by a clear delimiter that won't appear in normal text
    chunks_text = "\n\n" + "\n========== CHUNK BREAK =========\n\n".join(chunks) + "\n\n"
    
    # Clean text content for database storage
    def clean_text_for_db(text: str) -> str:
        """Clean text content for database storage."""
        if not text:
            return ""
        
        # Use enhanced sanitization if available, otherwise basic cleaning
        if SANITIZATION_AVAILABLE:
            return sanitize_text_for_database(text)
        else:
            # Remove null bytes which can cause database errors
            text = text.replace('\x00', '')
            
            # Limit length to prevent overly large entries (adjust as needed)
            max_length = 1000000  # 1MB limit
            if len(text) > max_length:
                text = text[:max_length]
                logger.warning(f"Text truncated to {max_length} characters for database storage")
            
            return text
    
    cleaned_chunks_text = clean_text_for_db(chunks_text)
    
    try:
        # Import database functions here to avoid circular imports
        from app.core.database import get_db
        from app.models.model import TestText
        
        # Get database session
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Create TestText record
            test_text_record = TestText(
                book=book_name,
                text=cleaned_chunks_text  # Store chunks as separated text
            )
            
            # Add to database
            db.add(test_text_record)
            await db.commit()
            await db.refresh(test_text_record)
            
            logger.info(f"Successfully stored {len(chunks)} chunks for '{book_name}' with ID: {test_text_record.id}")
            return test_text_record.id
            
        except Exception as db_error:
            logger.error(f"Database error while storing chunks: {db_error}")
            await db.rollback()
            return None
        finally:
            await db_gen.aclose()
            
    except Exception as e:
        logger.error(f"Error getting database session: {e}")
        return None



async def process_text_chunking_task(ctx: dict, teacher_id: str, file_path: str, gcs_file_name: str, knowledge_id: int, metadata: dict):
    """
    ARQ background task for processing text extraction and chunking.
    
    Args:
        ctx: ARQ context
        teacher_id: UUID string of the teacher (can be None for system/developer records)
        file_path: Path to the uploaded file
        gcs_file_name: File name in GCS
        knowledge_id: ID of the KnowledgeMetadata record
        metadata: Dictionary containing subject, notes, level, region, source_url, pillar, etc.
    """
    logger.info(f"🚀 Starting text extraction and chunking task for teacher {teacher_id}")
    logger.info(f"📁 File: {file_path}")
    logger.info(f"☁️ GCS Name: {gcs_file_name}")
    logger.info(f"📝 Metadata: {metadata}")
    
    # Import WebSocket functions
    try:
        from app.sch_ground.background import publish_ws_message, save_notification
    except ImportError as e:
        logger.error(f"Failed to import WebSocket functions: {e}")
        raise
    
    try:
        # Send initial status update via WebSocket (only if teacher_id is not None)
        if teacher_id is not None:
            await publish_ws_message(teacher_id, {
                "status": "processing",
                "message": f"Starting text extraction and chunking for {os.path.basename(file_path)}",
                "file_name": os.path.basename(file_path),
                "task_type": "text_chunking"
            })
        
        # Extract metadata fields
        subject = metadata.get("subject", "Unknown")
        notes = metadata.get("notes", "")
        level = metadata.get("level", "all levels")
        region = metadata.get("region", "all regions")
        source_url = metadata.get("source_url")
        file_path_field = metadata.get("file_path", gcs_file_name)
        pillar = metadata.get("pillar", "misc")
        
        # Create notes with filename if not provided
        file_name = os.path.basename(file_path)
        file_name_without_ext = Path(file_name).stem
        
        if notes:
            final_notes = f"{notes} ({file_name_without_ext})"
        else:
            final_notes = file_name_without_ext
            
        logger.info(f"📝 Final notes for knowledge metadata: {final_notes}")
        
        # Step 1: Extract text from PDF
        logger.info(f"Starting text extraction for: {file_path}")
        try:
            text_content = extract_text_from_pdf_pymupdf(file_path)
            logger.info(f"Extracted {len(text_content)} characters from document")
        except Exception as extraction_error:
            error_msg = str(extraction_error).lower()
            # Check for common file corruption or access errors
            if "corrupt" in error_msg or "damaged" in error_msg or "invalid" in error_msg or "cannot" in error_msg or "error" in error_msg:
                logger.error(f"File appears to be corrupted or inaccessible: {extraction_error}")
                # Send specific error notification via WebSocket for corrupted files (only if teacher_id is not None)
                if teacher_id is not None:
                    await publish_ws_message(teacher_id, {
                        "status": "error",
                        "message": f"Trouble processing file '{file_name}', might be a corrupted file.",
                        "file_name": file_name,
                        "error": "File corruption or access error",
                        "task_type": "text_chunking"
                    })
                
                # Save error notification (only if teacher_id is not None)
                if teacher_id is not None:
                    await save_notification(
                        teacher_id=teacher_id,
                        title="Text Extraction Failed",
                        message=f"Trouble processing file '{file_name}', might be a corrupted file.",
                        type_="error"
                    )
                
                raise RuntimeError(f"File appears to be corrupted or inaccessible: {extraction_error}")
            else:
                # Re-raise other extraction errors
                raise
        
        # Step 2: Chunk text using LangChain
        logger.info("Starting text chunking with LangChain")
        chunks = chunk_text_with_langchain(text_content)
        logger.info(f"Generated {len(chunks)} chunks from text")
        
        # Log chunk statistics
        if chunks:
            chunk_lengths = [len(chunk.split()) for chunk in chunks]  # Word count
            logger.info(f"Chunk word count statistics - Min: {min(chunk_lengths)}, Max: {max(chunk_lengths)}, Avg: {sum(chunk_lengths) // len(chunk_lengths)}")
        
        # Step 3: Update KnowledgeMetadata with chunk count
        logger.info(f"Updating KnowledgeMetadata record {knowledge_id} with chunk count: {len(chunks)}")
        
        # Update the KnowledgeMetadata record with chunk count
        try:
            from app.core.database import get_db
            from app.models.model import KnowledgeMetadata
            from sqlalchemy import update
            import asyncio
            
            # Retry mechanism for database operations
            max_retries = 3
            retry_delay = 1  # seconds
            
            for attempt in range(max_retries):
                try:
                    db_gen = get_db()
                    db = await db_gen.__anext__()
                    
                    try:
                        stmt = update(KnowledgeMetadata).where(KnowledgeMetadata.id == knowledge_id).values(
                            chunk_count=len(chunks)
                        )
                        await db.execute(stmt)
                        await db.commit()
                        logger.info(f"✅ Successfully updated KnowledgeMetadata record {knowledge_id} with chunk count: {len(chunks)}")
                        break  # Success, exit retry loop
                    except Exception as db_error:
                        await db.rollback()
                        if attempt == max_retries - 1:  # Last attempt
                            raise db_error
                        else:
                            logger.warning(f"⚠️ Database update attempt {attempt + 1} failed, retrying in {retry_delay}s: {db_error}")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                    finally:
                        await db_gen.aclose()
                except Exception as e:
                    if attempt == max_retries - 1:  # Last attempt
                        raise e
                    else:
                        logger.warning(f"⚠️ Database connection attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
        except Exception as e:
            logger.error(f"❌ Failed to update KnowledgeMetadata record {knowledge_id} after {max_retries} attempts: {e}")
            # Don't raise an exception here - we can continue with the rest of the processing
            # The chunk count is not critical for the overall workflow
            logger.warning("⚠️ Continuing processing without updating chunk count due to database error")
        
        # Step 4: Enqueue embedding task for the chunks
        logger.info("Enqueuing embedding task for the chunks")
        try:
            # Import the embedding enqueue function
            from app.rag_back.enqueue_embedding import enqueue_embedding_task
            
            # Prepare metadata for embedding task
            embedding_metadata = {
                "subject": subject,
                "notes": final_notes,
                "level": level,
                "region": region,
                "source_url": source_url,
                "file_path": file_path_field,
                "pillar": pillar
            }
            
            # Enqueue the embedding task
            embedding_job_id = await enqueue_embedding_task(
                teacher_id=teacher_id,
                knowledge_id=knowledge_id,  # Using the correct KnowledgeMetadata ID
                chunks=chunks,
                metadata=embedding_metadata
            )
            
            if embedding_job_id:
                logger.info(f"✅ Embedding task enqueued successfully with job ID: {embedding_job_id}")
            else:
                logger.error("❌ Failed to enqueue embedding task")
                
        except Exception as embedding_enqueue_error:
            logger.error(f"❌ Error enqueuing embedding task: {embedding_enqueue_error}")
            logger.error(traceback.format_exc())
            # We don't raise here because the chunking was successful, we just couldn't enqueue embedding
        
        # Send success notification via WebSocket (only if teacher_id is not None)
        if teacher_id is not None:
            await publish_ws_message(teacher_id, {
                "status": "completed",
                "message": f"Text extraction and chunking completed successfully for {file_name}",
                "file_name": file_name,
                "chunks_count": len(chunks),
                "knowledge_id": knowledge_id,
                "task_type": "text_chunking"
            })
        
        # Save success notification (only if teacher_id is not None)
        if teacher_id is not None:
            await save_notification(
                teacher_id=teacher_id,
                title="Text Extraction and Chunking Completed",
                message=f"Successfully processed {file_name} with {len(chunks)} chunks",
                type_="success"
            )
        
        return {
            "status": "success",
            "file_name": file_name,
            "chunks_count": len(chunks),
            "knowledge_id": knowledge_id
        }
        
    except Exception as e:
        error_msg = f"Text extraction and chunking failed for {file_path}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        # Send error notification via WebSocket (only if teacher_id is not None)
        if teacher_id is not None:
            await publish_ws_message(teacher_id, {
                "status": "error",
                "message": f"Text extraction and chunking failed for {os.path.basename(file_path)}: {str(e)}",
                "file_name": os.path.basename(file_path),
                "error": str(e),
                "task_type": "text_chunking"
            })
        
        raise
