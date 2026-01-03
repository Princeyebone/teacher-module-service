"""
Database Utilities

This module provides database connection and session utilities for the application.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from config import settings
import asyncio

# Initialize SQLAlchemy async engine
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=5,
    pool_recycle=180,
    pool_pre_ping=True
)

async def get_db():
    """
    Get database session generator.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSession(async_engine) as session:
        yield session

async def create_all_db_tables():
    """
    Create all database tables.
    
    This function initializes the database by creating all tables defined in the models.
    """
    # Import all models here to ensure they are registered with the metadata
    from model import SQLModel
    
    # Create all tables
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    print("✅ All database tables created successfully")