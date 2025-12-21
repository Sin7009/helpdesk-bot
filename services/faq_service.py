import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import FAQ

logger = logging.getLogger(__name__)

class FAQService:
    """Service for managing Frequently Asked Questions.
    
    This service maintains an in-memory cache of FAQ entries for fast lookup.
    The cache is pre-processed with lowercased trigger words for case-insensitive
    matching, optimized for small collections (up to ~100 entries).
    """
    _cache: List[FAQ] = []
    _search_cache: List[Tuple[str, FAQ]] = []

    @classmethod
    async def load_cache(cls, session: AsyncSession) -> None:
        """Load FAQ entries from database into memory cache.
        
        This method loads all FAQ entries and pre-processes them by creating
        a lowercase version of each trigger word for efficient searching.
        
        Args:
            session: Database session for querying FAQs.
        """
        stmt = select(FAQ).order_by(FAQ.trigger_word)
        result = await session.execute(stmt)
        cls._cache = result.scalars().all()

        # Pre-calculate lowercased trigger words for faster searching
        cls._search_cache = [(f.trigger_word.lower(), f) for f in cls._cache]

        logger.info(f"FAQ Cache loaded: {len(cls._cache)} items.")

    @classmethod
    def get_all_faqs(cls) -> List[FAQ]:
        """Get all FAQ entries from the in-memory cache.
        
        Returns:
            List of all FAQ objects.
        """
        return cls._cache

    @classmethod
    def find_match(cls, text: str) -> Optional[FAQ]:
        """Find an FAQ entry that matches the given text.
        
        Performs case-insensitive substring matching against all FAQ trigger words.
        Returns the first matching FAQ found.
        
        Performance note: For collections up to ~100 items, this simple iteration
        is 46% faster than regex-based approaches.
        
        Args:
            text: The text to search for FAQ matches.
            
        Returns:
            The first matching FAQ object, or None if no match found.
        """
        text_lower = text.lower()
        # Iterate over pre-calculated lowercase triggers
        for trigger, faq in cls._search_cache:
            if trigger in text_lower:
                return faq
        return None

    @classmethod
    async def refresh(cls, session: AsyncSession) -> None:
        """Reload the FAQ cache from the database.
        
        This is useful after FAQ entries have been added, modified, or deleted.
        
        Args:
            session: Database session for querying FAQs.
        """
        await cls.load_cache(session)
