import pytest
from unittest.mock import AsyncMock, MagicMock
from database.models import User, SourceType, UserRole
from services.user_service import get_or_create_user, ensure_admin_exists
from core.config import settings

@pytest.mark.asyncio
async def test_get_or_create_user_existing():
    session = AsyncMock()
    # Setup: Return an existing user
    existing_user = User(id=1, external_id=123, source=SourceType.TELEGRAM, username="existing")

    # Mock result
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing_user
    session.execute.return_value = result_mock

    user = await get_or_create_user(session, 123, SourceType.TELEGRAM)

    assert user == existing_user
    session.add.assert_not_called()

@pytest.mark.asyncio
async def test_get_or_create_user_new():
    session = AsyncMock()
    # Setup: Return None first
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    # Mock add (needs to be MagicMock, not AsyncMock)
    session.add = MagicMock()

    user = await get_or_create_user(session, 456, SourceType.TELEGRAM, username="new")

    assert user.external_id == 456
    assert user.username == "new"
    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(user)

@pytest.mark.asyncio
async def test_ensure_admin_exists_update_role():
    session = AsyncMock()
    # Setup: Admin exists but is a USER
    admin_user = User(id=1, external_id=settings.TG_ADMIN_ID, source=SourceType.TELEGRAM, role=UserRole.USER)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = admin_user
    session.execute.return_value = result_mock

    await ensure_admin_exists(session)

    assert admin_user.role == UserRole.ADMIN
    session.commit.assert_called_once()
    session.add.assert_not_called()

@pytest.mark.asyncio
async def test_ensure_admin_exists_create_new():
    session = AsyncMock()
    # Setup: Admin does not exist
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    session.add = MagicMock()

    await ensure_admin_exists(session)

    session.add.assert_called_once()
    args, _ = session.add.call_args
    created_user = args[0]
    assert created_user.external_id == settings.TG_ADMIN_ID
    assert created_user.role == UserRole.ADMIN
    session.commit.assert_called_once()
