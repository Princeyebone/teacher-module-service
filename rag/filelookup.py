#!/usr/bin/env python3
"""
File Lookup Script for KnowledgeMetadata Records

This script searches for PDF files in specified directories and checks if they exist 
in the KnowledgeMetadata table in the database.

Directories searched:
- Lesson
- curriculum
- Cognitive Science
- Evaluation
- Subject Mastery

Usage:
    python rag/filelookup.py
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Tuple
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Import project modules
from model import KnowledgeMetadata
from database import get_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('file_lookup_data.txt', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Directories to search
SEARCH_DIRECTORIES = [
    "Lesson",
    "curriculum",
    "Cognitive Science",
    "Evaluation",
    "Subject Mastery"
]

async def search_knowledge_metadata_by_filename(filename_without_ext: str, db: AsyncSession, is_curriculum: bool = False) -> List[KnowledgeMetadata]:
    """
    Search for KnowledgeMetadata records by filename (without extension) using pillar and file_path fields.
    
    Args:
        filename_without_ext: Filename without extension to search for
        db: Database session
        is_curriculum: Whether this is a curriculum file (search in file_path)
        
    Returns:
        List of KnowledgeMetadata records found
    """
    try:
        # Create multiple search patterns to handle different formatting variations
        search_patterns = [
            filename_without_ext,  # Exact match
            filename_without_ext.replace('_', ' '),  # Underscores to spaces
            filename_without_ext.replace(' ', '_'),  # Spaces to underscores
            filename_without_ext.replace('-', ' '),  # Hyphens to spaces
            filename_without_ext.replace(' ', '-'),  # Spaces to hyphens
        ]
        
        # Remove duplicates and empty strings
        search_patterns = list(set(filter(None, search_patterns)))
        
        logger.debug(f"Searching for filename variations: {search_patterns}")
        
        # Build conditions for all patterns
        conditions = []
        params = {}
        
        for i, pattern in enumerate(search_patterns):
            param_name_path = f"search_path_{i}"
            param_name_pillar = f"search_pillar_{i}"
            params[param_name_path] = f"%{pattern}%"
            params[param_name_pillar] = f"%{pattern}%"
            
            # Search in file_path and pillar fields for all files
            conditions.append(f"file_path ILIKE :{param_name_path}")
            conditions.append(f"pillar ILIKE :{param_name_pillar}")
        
        # Combine all conditions
        all_conditions = " OR ".join(conditions)
        
        # Query for records
        stmt = select(KnowledgeMetadata).where(text(all_conditions))
        
        result = await db.execute(stmt, params)
        records = result.scalars().all()
        
        return list(records)
        
    except Exception as e:
        logger.error(f"Error searching for KnowledgeMetadata records: {e}")
        return []

async def process_directory(directory_path: Path) -> Tuple[List[str], List[str]]:
    """
    Process a directory and check if its files exist in KnowledgeMetadata.
    
    Args:
        directory_path: Path to the directory to process
        
    Returns:
        Tuple of (found_files, missing_files)
    """
    found_files = []
    missing_files = []
    
    # Check if this is a curriculum directory
    is_curriculum = directory_path.name == "curriculum"
    
    logger.info(f"📁 Processing directory: {directory_path} {'(curriculum files)' if is_curriculum else ''}")
    
    # Get all PDF files in the directory
    pdf_files = list(directory_path.glob("*.pdf"))
    logger.info(f"   Found {len(pdf_files)} PDF files")
    
    if not pdf_files:
        logger.info(f"   No PDF files found in {directory_path}")
        return found_files, missing_files
    
    # Create database session
    db_gen = get_db()
    db = await db_gen.__anext__()
    
    try:
        for file_path in pdf_files:
            filename_without_ext = file_path.stem
            logger.info(f"   Checking file: {filename_without_ext}")
            
            # Search for KnowledgeMetadata records
            records = await search_knowledge_metadata_by_filename(filename_without_ext, db, is_curriculum)
            
            if records:
                logger.info(f"   ✅ FOUND: {filename_without_ext} - {len(records)} record(s)")
                found_files.append(str(file_path))
                
                # Log details of found records
                for record in records:
                    logger.info(f"      ID: {record.id}, Pillar: '{record.pillar}', File path: {record.file_path}")
            else:
                logger.info(f"   ❌ MISSING: {filename_without_ext}")
                missing_files.append(str(file_path))
                
    except Exception as e:
        logger.error(f"Error processing directory {directory_path}: {e}")
    finally:
        await db_gen.aclose()
    
    return found_files, missing_files

async def main():
    """Main function to run the file lookup process."""
    logger.info("=" * 60)
    logger.info("FILE LOOKUP FOR KNOWLEDGE METADATA RECORDS")
    logger.info("=" * 60)
    
    all_found_files = []
    all_missing_files = []
    
    # Process each directory
    for dir_name in SEARCH_DIRECTORIES:
        dir_path = Path(dir_name)
        
        if not dir_path.exists():
            logger.warning(f"⚠️  Directory not found: {dir_path}")
            continue
            
        if not dir_path.is_dir():
            logger.warning(f"⚠️  Path is not a directory: {dir_path}")
            continue
            
        found_files, missing_files = await process_directory(dir_path)
        all_found_files.extend(found_files)
        all_missing_files.extend(missing_files)
        
        logger.info(f"   Directory summary - Found: {len(found_files)}, Missing: {len(missing_files)}")
        logger.info("-" * 40)
    
    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files found in database: {len(all_found_files)}")
    logger.info(f"Total files missing from database: {len(all_missing_files)}")
    
    if all_found_files:
        logger.info("\n✅ FILES FOUND IN DATABASE:")
        for file_path in all_found_files:
            logger.info(f"   {file_path}")
    
    if all_missing_files:
        logger.info("\n❌ FILES MISSING FROM DATABASE:")
        for file_path in all_missing_files:
            logger.info(f"   {file_path}")
    
    logger.info("=" * 60)
    logger.info("FILE LOOKUP COMPLETED")
    logger.info("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n💥 Unexpected error: {e}")
        sys.exit(1)