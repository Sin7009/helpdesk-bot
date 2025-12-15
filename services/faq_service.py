import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import FAQ

logger = logging.getLogger(__name__)

class FAQService:
    _cache: List[FAQ] = []
    _search_cache: List[Tuple[str, FAQ]] = []

    @classmethod
    async def load_cache(cls, session: AsyncSession):
        """Loads FAQ from database to memory."""
        stmt = select(FAQ).order_by(FAQ.trigger_word)
        result = await session.execute(stmt)
        cls._cache = result.scalars().all()

        # Pre-calculate lowercased trigger words for faster searching
        cls._search_cache = [(f.trigger_word.lower(), f) for f in cls._cache]

        logger.info(f"FAQ Cache loaded: {len(cls._cache)} items.")

    @classmethod
    def get_all_faqs(cls) -> List[FAQ]:
        """Returns all FAQs from the in-memory cache."""
        return cls._cache

    @classmethod
    def find_match(cls, text: str) -> Optional[FAQ]:
        text_lower = text.lower()
        # Iterate over pre-calculated lowercase triggers
        for trigger, faq in cls._search_cache:
            if trigger in text_lower:
                return faq
        return None

    @classmethod
    async def refresh(cls, session: AsyncSession):
        await cls.load_cache(session)
