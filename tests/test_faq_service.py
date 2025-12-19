import pytest
from unittest.mock import AsyncMock, MagicMock
from services.faq_service import FAQService
from database.models import FAQ

@pytest.fixture(autouse=True)
def reset_faq_cache():
    # Reset cache before and after each test
    FAQService._cache = []
    FAQService._search_cache = []
    yield
    FAQService._cache = []
    FAQService._search_cache = []

@pytest.mark.asyncio
async def test_load_cache():
    session = AsyncMock()

    faq1 = FAQ(id=1, trigger_word="Price", answer_text="100$")
    faq2 = FAQ(id=2, trigger_word="Help", answer_text="Contact support")

    # Mock result.scalars().all()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [faq1, faq2]
    session.execute.return_value = result_mock

    await FAQService.load_cache(session)

    assert len(FAQService._cache) == 2
    assert len(FAQService._search_cache) == 2
    assert FAQService._search_cache[0][0] == "price"
    assert FAQService._search_cache[1][0] == "help"

@pytest.mark.asyncio
async def test_find_match():
    # Setup cache manually to test find_match logic in isolation or via load_cache
    faq = FAQ(id=1, trigger_word="Price", answer_text="100$")
    FAQService._cache = [faq]
    FAQService._search_cache = [("price", faq)]

    # Exact match
    match = FAQService.find_match("What is the price?")
    assert match == faq

    # Case insensitive
    match = FAQService.find_match("PRICE please")
    assert match == faq

    # No match
    match = FAQService.find_match("Hello world")
    assert match is None

@pytest.mark.asyncio
async def test_refresh():
    session = AsyncMock()
    faq = FAQ(id=1, trigger_word="New", answer_text="Data")

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [faq]
    session.execute.return_value = result_mock

    await FAQService.refresh(session)

    assert len(FAQService._cache) == 1
    assert FAQService._cache[0].trigger_word == "New"
