import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import FAQ

logger = logging.getLogger(__name__)

class FAQService:
    _cache: List[FAQ] = []

    @classmethod
    async def load_cache(cls, session: AsyncSession):
        """Loads FAQ from database to memory."""
        stmt = select(FAQ).order_by(FAQ.trigger_word)
        result = await session.execute(stmt)
        cls._cache = result.scalars().all()
        logger.info(f"FAQ Cache loaded: {len(cls._cache)} items.")

    @classmethod
    def get_cache(cls) -> List[FAQ]:
        return cls._cache

    @classmethod
    def find_match(cls, text: str) -> Optional[FAQ]:
        text_lower = text.lower()
        for faq in cls._cache:
            if faq.trigger_word.lower() in text_lower:
                return faq
        return None

    @classmethod
    async def refresh(cls, session: AsyncSession):
        await cls.load_cache(session)
