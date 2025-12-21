from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Category
from database.repositories.base import BaseRepository

class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Category)

    async def get_by_name(self, name: str) -> Optional[Category]:
        stmt = select(Category).where(Category.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
