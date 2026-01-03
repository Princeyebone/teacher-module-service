#!/usr/bin/env python3
"""
Text extraction using unstructured.io for PDF files in the Evaluation directory.
Extracts text from PDFs using unstructured.io and stores it in the TestText database table.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List
from unstructured.partition.auto import partition

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

# Import modules
try:
    from database import get_db
    from model import TestText
    logger.info("✅ All modules imported successfully")
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    sys.exit(1)

def extract_text_from_pdf_unstructured(file_path: str) -> str:
    """
    Extract text from PDF using unstructured.io.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
    """
    logger.info(f"Starting unstructured.io extraction for: {file_path}")
    
    try:
        # Use unstructured.io to partition the PDF
        elements = partition(file_path)
        
        # Extract text from all elements
        text_content = ""
        for element in elements:
            if hasattr(element, 'text') and element.text:
                text_content += element.text + "\n"
        
        logger.info(f"Unstructured.io extraction completed. Extracted {len(text_content)} characters from {len(elements)} elements.")
        return text_content.strip()
        
    except Exception as e:
        logger.error(f"Error during unstructured.io extraction: {e}")
        raise

async def store_text_in_database(book_name: str, text_content: str) -> bool:
    """
    Store extracted text in the TestText database table.
    
    Args:
        book_name: Name of the book/PDF file
        text_content: Extracted text content
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Storing text for '{book_name}' in database")
    
    try:
        # Get database session
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Create TestText record
            test_text_record = TestText(
                book=book_name,
                text=text_content
            )
            
            # Add to database
            db.add(test_text_record)
            await db.commit()
            await db.refresh(test_text_record)
            
            logger.info(f"Successfully stored text for '{book_name}' with ID: {test_text_record.id}")
            return True
            
        except Exception as db_error:
            logger.error(f"Database error while storing text: {db_error}")
            await db.rollback()
            return False
        finally:
            await db_gen.aclose()
            
    except Exception as e:
        logger.error(f"Error getting database session: {e}")
        return False

async def process_single_pdf(file_path: str) -> bool:
    """
    Process a single PDF file: extract text using unstructured.io and store in database.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        True if successful, False otherwise
    """
    filename = os.path.basename(file_path)
    logger.info(f"🚀 Processing PDF file: {filename}")
    
    if not os.path.exists(file_path):
        logger.error(f"❌ File does not exist: {file_path}")
        return False
    
    try:
        # Extract text from PDF using unstructured.io
        text_content = extract_text_from_pdf_unstructured(file_path)
        
        # Store in database
        success = await store_text_in_database(filename, text_content)
        
        if success:
            logger.info(f"🎉 Successfully processed and stored {filename}")
        else:
            logger.error(f"❌ Failed to store {filename} in database")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error processing file {filename}: {str(e)}")
        return False

async def process_all_evaluation_pdfs() -> None:
    """Process all PDF files in the Evaluation directory using unstructured.io and store text in TestText table."""
    evaluation_dir = Path("Evaluation")
    
    if not evaluation_dir.exists():
        logger.error(f"❌ Evaluation directory not found: {evaluation_dir.absolute()}")
        return
    
    pdf_files = list(evaluation_dir.glob("*.pdf"))
    logger.info(f"📁 Found {len(pdf_files)} PDF files in Evaluation directory")
    
    if not pdf_files:
        logger.info("No PDF files found in Evaluation directory")
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
            logger.error(f"💥 Unexpected error processing {pdf_file.name}: {str(e)}")
        
        # Small delay between files to prevent overwhelming the system
        if i < len(pdf_files):
            await asyncio.sleep(1)
    
    logger.info(f"\n{'='*80}")
    logger.info("📊 BATCH PROCESSING SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Total files: {len(pdf_files)}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed: {failed_count}")

if __name__ == "__main__":
    logger.info("🚀 Starting unstructured.io text extraction and storage process")
    
    try:
        asyncio.run(process_all_evaluation_pdfs())
        logger.info("🏁 Unstructured.io text extraction and storage process completed")
    except KeyboardInterrupt:
        logger.info("🛑 Unstructured.io text extraction and storage process interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unstructured.io text extraction and storage process failed: {str(e)}")