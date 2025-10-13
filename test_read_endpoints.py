#!/usr/bin/env python3
"""
Test script to verify that the read endpoints are working correctly
after removing TempExtract dependency.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from uuid import UUID
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the models
from model import Strand, Substrand, ContentStandard, Indicator, TeacherProfile
from config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_read_endpoints():
    """Test the read endpoints by directly querying the database"""
    # Create database engine
    DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    engine = create_async_engine(DATABASE_URL)
    
    # Test teacher ID (replace with an actual teacher ID from your database)
    teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"  # Example UUID
    
    try:
        async with AsyncSession(engine) as session:
            # Test 1: Read strands
            logger.info("=== Testing Read Strands ===")
            strand_query = select(Strand).where(Strand.teacher_id == UUID(teacher_id))
            strand_result = await session.execute(strand_query)
            strands = strand_result.scalars().all()
            logger.info(f"Found {len(strands)} strands")
            
            for strand in strands[:3]:  # Show first 3
                logger.info(f"  - Strand: {strand.strand_name}, Subject: {strand.subject}, Week: {strand.week_number}")
            
            # Test 2: Read substrands
            logger.info("=== Testing Read Substrands ===")
            substrand_query = select(Substrand).where(Substrand.teacher_id == UUID(teacher_id))
            substrand_result = await session.execute(substrand_query)
            substrands = substrand_result.scalars().all()
            logger.info(f"Found {len(substrands)} substrands")
            
            for substrand in substrands[:3]:  # Show first 3
                logger.info(f"  - Substrand: {substrand.substrand_name}, Strand ID: {substrand.strand_id}")
                
                # Get the strand name for context
                strand_query = select(Strand).where(Strand.id == substrand.strand_id)
                strand_result = await session.execute(strand_query)
                strand = strand_result.scalar_one_or_none()
                if strand:
                    logger.info(f"    -> Strand: {strand.strand_name}")
            
            # Test 3: Read content standards
            logger.info("=== Testing Read Content Standards ===")
            cs_query = select(ContentStandard).where(ContentStandard.teacher_id == UUID(teacher_id))
            cs_result = await session.execute(cs_query)
            content_standards = cs_result.scalars().all()
            logger.info(f"Found {len(content_standards)} content standards")
            
            for cs in content_standards[:3]:  # Show first 3
                logger.info(f"  - Content Standard: {cs.content_standard_code or 'No Code'} - {cs.content_standard[:50]}...")
                
                # Get the substrand for context
                substrand_query = select(Substrand).where(Substrand.id == cs.substrand_id)
                substrand_result = await session.execute(substrand_query)
                substrand = substrand_result.scalar_one_or_none()
                if substrand:
                    logger.info(f"    -> Substrand: {substrand.substrand_name}")
            
            # Test 4: Read indicators
            logger.info("=== Testing Read Indicators ===")
            indicator_query = select(Indicator).where(Indicator.teacher_id == UUID(teacher_id))
            indicator_result = await session.execute(indicator_query)
            indicators = indicator_result.scalars().all()
            logger.info(f"Found {len(indicators)} indicators")
            
            for indicator in indicators[:3]:  # Show first 3
                logger.info(f"  - Indicator: {indicator.indicator_code or 'No Code'} - {indicator.indicator_text[:50]}...")
                
                # Get the content standard for context
                cs_query = select(ContentStandard).where(ContentStandard.id == indicator.content_standard_id)
                cs_result = await session.execute(cs_query)
                cs = cs_result.scalar_one_or_none()
                if cs:
                    logger.info(f"    -> Content Standard: {cs.content_standard_code or 'No Code'}")
            
            logger.info("=== Test Completed Successfully ===")
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_read_endpoints())