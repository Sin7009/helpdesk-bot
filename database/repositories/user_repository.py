from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, SourceType
from database.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_external_id(self, external_id: int, source: str) -> Optional[User]:
        stmt = select(User).where(User.external_id == external_id, User.source == source)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_obj, source: str = SourceType.TELEGRAM) -> User:
        """
        Get existing user or create a new one based on Telegram message.from_user.
        """
        user = await self.get_by_external_id(user_obj.id, source)

        if not user:
            user = User(
                external_id=user_obj.id,
                source=source,
                username=user_obj.username,
                full_name=user_obj.full_name
            )
            self.session.add(user)
            await self.session.flush()
        else:
            # Update info if changed
            if user.full_name != user_obj.full_name or user.username != user_obj.username:
                user.full_name = user_obj.full_name
                user.username = user_obj.username
                await self.session.flush()

        return user

    async def update_profile(
        self,
        external_id: int,
        course: int = None,
        group: str = None,
        is_head_student: bool = None,
        source: str = SourceType.TELEGRAM
    ) -> Optional[User]:
        """
        Update user profile fields.
        """
        user = await self.get_by_external_id(external_id, source)
        if user:
            if course is not None:
                user.course = course
            if group is not None:
                user.group_number = group
            if is_head_student is not None:
                user.is_head_student = is_head_student

            await self.session.commit()
        return user
