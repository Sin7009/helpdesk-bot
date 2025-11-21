from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
import os

DATABASE_URL = "sqlite+aiosqlite:///./support.db"

engine = create_async_engine(DATABASE_URL, echo=True)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # For dev only, be careful
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
