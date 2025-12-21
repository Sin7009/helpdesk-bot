from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from database.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_external_id(self, external_id: int, source: str) -> Optional[User]:
        stmt = select(User).where(User.external_id == external_id, User.source == source)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
