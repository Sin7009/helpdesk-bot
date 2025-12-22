import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from database.models import Base
from core.config import settings

# Get database URL from config (supports both SQLite and PostgreSQL)
DATABASE_URL = settings.get_database_url()

# Echo SQL queries only in development (when DEBUG env var is set)
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

# Determine if using PostgreSQL for connection pool settings
_is_postgresql = DATABASE_URL.startswith("postgresql")

# Configure engine with appropriate settings for the database type
# PostgreSQL uses NullPool by default for async to avoid connection issues
# SQLite uses the default pool
if _is_postgresql:
    engine = create_async_engine(
        DATABASE_URL, 
        echo=DEBUG_MODE,
        poolclass=NullPool,  # Recommended for async PostgreSQL
    )
else:
    engine = create_async_engine(DATABASE_URL, echo=DEBUG_MODE)

# ВАЖНО: Называем переменную new_session, чтобы handlers.telegram мог её найти
new_session = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def init_db():
    """Initialize the database by creating all tables."""
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Раскомментируй, если надо сбросить базу
        await conn.run_sync(Base.metadata.create_all)


def get_database_url() -> str:
    """Return the currently configured database URL.
    
    Returns:
        str: The database URL being used
    """
    return DATABASE_URL


def is_postgresql() -> bool:
    """Check if the current database is PostgreSQL.
    
    Returns:
        bool: True if using PostgreSQL, False otherwise (SQLite)
    """
    return _is_postgresql
