from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from core.config import settings

# Используем путь из конфига (важно для Docker volume)
DATABASE_URL = f"sqlite+aiosqlite:///{settings.DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=True)

# ВАЖНО: Называем переменную new_session, чтобы handlers.telegram мог её найти
new_session = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Раскомментируй, если надо сбросить базу
        await conn.run_sync(Base.metadata.create_all)
