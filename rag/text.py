#!/usr/bin/env python3
"""
Text extraction and chunking tool for PDF files in the Lesson directory.
Extracts text from PDFs, chunks it using LangChain, and stores the chunks in the TestText database table.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
import fitz  # PyMuPDF
from datetime import datetime

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

# Create detailed log file
LOG_FILE = "text_extraction_detailed.log"
DETAILED_LOGGER = logging.getLogger("detailed_logger")
detailed_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
detailed_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
DETAILED_LOGGER.addHandler(detailed_handler)
DETAILED_LOGGER.setLevel(logging.INFO)

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract or PIL not available. OCR fallback disabled.")

# Import modules
try:
    from database import get_db
    from model import TestText
    logger.info("✅ All modules imported successfully")
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    sys.exit(1)

# Try to import LangChain for chunking
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
    logger.info("✅ LangChain available for chunking")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("⚠️ LangChain not available. Will use basic chunking.")


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
    
    # Log if we removed any characters
    if len(cleaned) != len(text_content):
        removed_chars = len(text_content) - len(cleaned)
        logger.info(f"Cleaned {removed_chars} problematic characters from text")
        DETAILED_LOGGER.info(f"[TEXT_CLEANED] Removed {removed_chars} problematic characters")
    
    return cleaned


def sanitize_text_for_database(text: str) -> str:
    """
    Enhanced text sanitization for database storage.
    Removes null bytes and other problematic UTF-8 sequences.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text safe for database storage
    """
    if not text:
        return text
        
    # Remove null bytes specifically (the main issue in the error)
    sanitized = text.replace('\x00', '')
    
    # Remove other control characters that might cause issues
    sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in ['\n', '\t', '\r'])
    
    # Strip excessive whitespace
    sanitized = ' '.join(sanitized.split())
    
    return sanitized

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
    DETAILED_LOGGER.info(f"[START] Processing file: {filename}")
    
    text_content = ""
    ocr_pages = []
    extracted_pages = []
    
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info(f"Processing PDF with {total_pages} pages")
        DETAILED_LOGGER.info(f"[INFO] PDF has {total_pages} pages")
        
        for page_num, page in enumerate(doc):
            # Get text content from the page
            page_text = page.get_text()
            text_content += page_text
            extracted_pages.append(page_num + 1)
            
            # Check if page has very little text (likely scanned image)
            # Threshold: less than 50 characters for a whole page
            if len(page_text.strip()) < 50 and OCR_AVAILABLE:
                logger.info(f"Page {page_num + 1} has low text content ({len(page_text.strip())} chars). Attempting OCR...")
                DETAILED_LOGGER.info(f"[OCR] Page {page_num + 1} has low text content ({len(page_text.strip())} chars). Attempting OCR...")
                try:
                    # Render page to image
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Perform OCR with timeout to prevent hanging
                    try:
                        ocr_text = pytesseract.image_to_string(img, timeout=30)  # 30 second timeout
                    except Exception as timeout_e:
                        logger.warning(f"OCR timed out for page {page_num + 1}: {timeout_e}")
                        DETAILED_LOGGER.warning(f"[OCR_TIMEOUT] Page {page_num + 1}: OCR timed out - {timeout_e}")
                        ocr_text = ""  # Treat timeout as no text extracted
                        
                    if ocr_text.strip():
                        logger.info(f"OCR successful for page {page_num + 1}. Extracted {len(ocr_text)} chars.")
                        DETAILED_LOGGER.info(f"[OCR_SUCCESS] Page {page_num + 1}: OCR successful - {len(ocr_text)} characters extracted")
                        text_content += f"\n{ocr_text.strip()}\n"
                        ocr_pages.append(page_num + 1)
                    else:
                        logger.warning(f"OCR yielded no text for page {page_num + 1}")
                        DETAILED_LOGGER.warning(f"[OCR_EMPTY] Page {page_num + 1}: OCR yielded no text")
                        # If OCR failed but we had some original text, keep it
                        if page_text.strip():
                            text_content += page_text
                except Exception as ocr_e:
                    logger.error(f"OCR failed for page {page_num + 1}: {ocr_e}")
                    DETAILED_LOGGER.error(f"[OCR_FAILED] Page {page_num + 1}: OCR failed - {ocr_e}")
                    # Fallback to whatever we extracted originally
                    if page_text.strip():
                        text_content += page_text
            else:
                # Log normal extraction
                DETAILED_LOGGER.info(f"[EXTRACTED] Page {page_num + 1}: {len(page_text.strip())} characters extracted")
        
        doc.close()
        
        # Log summary
        total_chars = len(text_content)
        total_words = len(text_content.split())
        logger.info(f"PyMuPDF extraction completed. Extracted {total_chars} characters, {total_words} words.")
        DETAILED_LOGGER.info(f"[SUCCESS] File: {filename} | Pages: {total_pages} | Characters: {total_chars} | Words: {total_words} | OCR Pages: {len(ocr_pages)} | Extracted Pages: {len(extracted_pages)}")
        
        if ocr_pages:
            DETAILED_LOGGER.info(f"[OCR_PAGES] OCR performed on pages: {ocr_pages}")
        if extracted_pages:
            DETAILED_LOGGER.info(f"[EXTRACTED_PAGES] Text extracted from pages: {extracted_pages}")
            
        return text_content.strip()
        
    except Exception as e:
        logger.error(f"Internal PyMuPDF error: {e}")
        DETAILED_LOGGER.error(f"[FAILED] File: {filename} | Error: {e}")
        DETAILED_LOGGER.exception(f"[EXCEPTION_DETAILS] File: {filename} | Exception details:")
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

async def store_chunks_in_database(book_name: str, chunks: List[str]) -> bool:
    """;
    Store chunks in the TestText database table as concatenated text with separators.
    
    Args:
        book_name: Name of the book/PDF file
        chunks: List of chunked text strings
        
    Returns:
        True if successful, False otherwise
    """;
    logger.info(f"Storing {len(chunks)} chunks for '{book_name}' in database")
    
    if not chunks:
        logger.warning(f"No chunks to store for '{book_name}'")
        chunks = ["No content extracted from this document."]
    
    # Join chunks with clear separators for easy viewing
    # Each chunk is separated by a clear delimiter that won't appear in normal text
    chunks_text = "\n\n" + "\n========== CHUNK BREAK =========\n\n".join(chunks) + "\n\n"
    
    # Clean text content to remove null bytes and other problematic characters
    cleaned_chunks_text = clean_text_for_db(chunks_text)
    
    try:
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
            DETAILED_LOGGER.info(f"[STORED] File: {book_name} | Database ID: {test_text_record.id} | Chunks: {len(chunks)}")
            return True
            
        except Exception as db_error:
            logger.error(f"Database error while storing chunks: {db_error}")
            DETAILED_LOGGER.error(f"[DB_FAILED] File: {book_name} | Database error: {db_error}")
            DETAILED_LOGGER.exception(f"[DB_EXCEPTION_DETAILS] File: {book_name} | Database exception details:")
            await db.rollback()
            return False
        finally:
            await db_gen.aclose()
            
    except Exception as e:
        logger.error(f"Error getting database session: {e}")
        DETAILED_LOGGER.error(f"[SESSION_FAILED] File: {book_name} | Session error: {e}")
        return False

async def process_single_pdf(file_path: str) -> bool:
    """;
    Process a single PDF file: extract text, chunk it, and store chunks in database.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        True if successful, False otherwise
    """;
    filename = os.path.basename(file_path)
    logger.info(f"🚀 Processing PDF file: {filename}")
    DETAILED_LOGGER.info(f"[PROCESSING] Starting processing for file: {filename}")
    
    if not os.path.exists(file_path):
        error_msg = f"❌ File does not exist: {file_path}"
        logger.error(error_msg)
        DETAILED_LOGGER.error(f"[FILE_NOT_FOUND] File: {filename} | Error: File does not exist")
        return False
    
    try:
        # Extract text from PDF
        text_content = extract_text_from_pdf_pymupdf(file_path)
        
        # Chunk the extracted text
        chunks = chunk_text_with_langchain(text_content)
        logger.info(f"✅ Created {len(chunks)} chunks from extracted text")
        DETAILED_LOGGER.info(f"[CHUNKED] File: {filename} | Chunks created: {len(chunks)}")
        
        # Store chunks in database
        success = await store_chunks_in_database(filename, chunks)
        
        if success:
            logger.info(f"🎉 Successfully processed and stored {len(chunks)} chunks for {filename}")
            DETAILED_LOGGER.info(f"[COMPLETED] File: {filename} | Status: SUCCESS | Chunks: {len(chunks)}")
        else:
            logger.error(f"❌ Failed to store chunks for {filename} in database")
            DETAILED_LOGGER.error(f"[COMPLETED] File: {filename} | Status: FAILED | Database storage failed")
            
        return success
        
    except Exception as e:
        error_msg = f"❌ Error processing file {filename}: {str(e)}"
        logger.error(error_msg)
        DETAILED_LOGGER.error(f"[COMPLETED] File: {filename} | Status: FAILED | Error: {str(e)}")
        DETAILED_LOGGER.exception(f"[EXCEPTION_DETAILS] File: {filename} | Exception details:")
        return False

async def process_all_lesson_pdfs() -> None:
    """Process all PDF files in the Lesson directory and store text in TestText table."""
    lesson_dir = Path("Lesson")
    
    if not lesson_dir.exists():
        error_msg = f"❌ Lesson directory not found: {lesson_dir.absolute()}"
        logger.error(error_msg)
        DETAILED_LOGGER.error(f"[DIRECTORY_ERROR] Lesson directory not found: {lesson_dir.absolute()}")
        return
    
    pdf_files = list(lesson_dir.glob("*.pdf"))
    logger.info(f"📁 Found {len(pdf_files)} PDF files in Lesson directory")
    DETAILED_LOGGER.info(f"[START_BATCH] Found {len(pdf_files)} PDF files in Lesson directory")
    
    if not pdf_files:
        logger.info("No PDF files found in Lesson directory")
        DETAILED_LOGGER.info("[NO_FILES] No PDF files found in Lesson directory")
        return
    
    successful_count = 0
    failed_count = 0
    
    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"📄 Processing file {i}/{len(pdf_files)}: {pdf_file.name}")
        logger.info(f"{'='*80}")
        
        try:
            success = await process_single_pdf(str(pdf_file))
            if success:
                successful_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            failed_count += 1
            error_msg = f"💥 Unexpected error processing {pdf_file.name}: {str(e)}"
            logger.error(error_msg)
            DETAILED_LOGGER.error(f"[UNEXPECTED_ERROR] File: {pdf_file.name} | Error: {str(e)}")
        
        # Small delay between files to prevent overwhelming the system
        if i < len(pdf_files):
            await asyncio.sleep(1)
    
    logger.info(f"\n{'='*80}")
    logger.info("📊 BATCH PROCESSING SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total files: {len(pdf_files)}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed: {failed_count}")
    
    summary_msg = f"[BATCH_SUMMARY] Total files: {len(pdf_files)}, Successful: {successful_count}, Failed: {failed_count}"
    DETAILED_LOGGER.info(summary_msg)

if __name__ == "__main__":
    logger.info("🚀 Starting text extraction and storage process")
    DETAILED_LOGGER.info("[PROCESS_STARTED] Text extraction and storage process started")
    
    try:
        asyncio.run(process_all_lesson_pdfs())
        logger.info("🏁 Text extraction and storage process completed")
        DETAILED_LOGGER.info("[PROCESS_COMPLETED] Text extraction and storage process completed successfully")
    except KeyboardInterrupt:
        logger.info("🛑 Text extraction and storage process interrupted by user")
        DETAILED_LOGGER.info("[PROCESS_INTERRUPTED] Text extraction and storage process interrupted by user")
    except Exception as e:
        logger.error(f"💥 Text extraction and storage process failed: {str(e)}")
        DETAILED_LOGGER.error(f"[PROCESS_FAILED] Text extraction and storage process failed: {str(e)}")