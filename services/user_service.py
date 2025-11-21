from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, SourceType

async def get_or_create_user(
    session: AsyncSession,
    external_id: int,
    source: SourceType,
    username: str | None = None,
    full_name: str | None = None,
) -> User:
    """
    Retrieves an existing user by external ID and source, or creates a new one if not found.

    This function performs a database lookup to check if a user with the given
    external_id (from Telegram or VK) and source platform already exists.
    If the user exists, it is returned.
    If not, a new User record is created, added to the session, committed, and refreshed.

    Args:
        session (AsyncSession): The database session.
        external_id (int): The user's ID on the external platform (TG/VK).
        source (SourceType): The platform source ('tg' or 'vk').
        username (str | None): The username on the platform (optional).
        full_name (str | None): The full name of the user (optional).

    Returns:
        User: The retrieved or created User object.
    """
    stmt = select(User).where(User.external_id == external_id, User.source == source)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            external_id=external_id,
            source=source,
            username=username,
            full_name=full_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user
