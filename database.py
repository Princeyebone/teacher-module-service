from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel
from config import settings

# Configure async engine with explicit connection pool settings
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=20,           # Max number of connections in the pool
    max_overflow=40,        # Allow up to 40 additional connections under load
    pool_timeout=60,        # Wait up to 60 seconds for a connection
    pool_recycle=900        # Recycle connections every 15 minutes to prevent stale connections
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def create_all_db_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)