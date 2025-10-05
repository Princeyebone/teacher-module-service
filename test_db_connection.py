import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from model import TempExtract
from config import settings
from uuid import UUID
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_db_connection():
    """Test database connection and TempExtract table operations"""
    logger.info("Testing database connection...")
    
    # Create engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=5,
        pool_recycle=180,
        pool_pre_ping=True
    )
    
    try:
        # Test connection
        async with engine.connect() as conn:
            logger.info("✅ Database connection successful")
            
            # Test TempExtract table
            async with AsyncSession(engine) as session:
                # Try to query the table
                try:
                    stmt = select(TempExtract).limit(1)
                    result = await session.execute(stmt)
                    logger.info("✅ TempExtract table accessible")
                except Exception as e:
                    logger.error(f"❌ Error accessing TempExtract table: {e}")
                    return
                
                # Try to create a test entry
                try:
                    test_data = {
                        "test": "data",
                        "timestamp": "2025-10-03T16:50:28.954Z"
                    }
                    
                    test_entry = TempExtract(
                        teacher_id=UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82"),
                        type="test_entry",
                        data=test_data
                    )
                    
                    session.add(test_entry)
                    await session.commit()
                    logger.info("✅ Successfully created test TempExtract entry")
                    
                    # Verify it was saved
                    stmt = select(TempExtract).where(
                        TempExtract.teacher_id == UUID("7bed2b69-8000-4b36-8e91-7fe0b70c9d82"),
                        TempExtract.type == "test_entry"
                    )
                    result = await session.execute(stmt)
                    saved_entry = result.scalar_one_or_none()
                    if saved_entry:
                        logger.info(f"✅ Verified test entry saved with ID: {saved_entry.id}")
                        logger.info(f"✅ Test entry data: {saved_entry.data}")
                        
                        # Clean up test entry
                        await session.delete(saved_entry)
                        await session.commit()
                        logger.info("✅ Cleaned up test entry")
                    else:
                        logger.error("❌ Failed to verify test entry was saved")
                        
                except Exception as e:
                    logger.error(f"❌ Error creating test TempExtract entry: {e}")
                    logger.error(f"Full traceback: {e}", exc_info=True)
                    
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.error(f"Full traceback: {e}", exc_info=True)
    finally:
        await engine.dispose()
        logger.info("Database connection closed")

if __name__ == "__main__":
    asyncio.run(test_db_connection())