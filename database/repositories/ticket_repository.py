import datetime
from typing import Optional, List
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload, contains_eager
from sqlalchemy.exc import IntegrityError
from database.models import Ticket, User, TicketStatus, DailyTicketCounter
from database.repositories.base import BaseRepository

class TicketRepository(BaseRepository[Ticket]):
    def __init__(self, session):
        super().__init__(session, Ticket)

    async def get_active_by_user(self, user_id: int, source: str) -> Optional[Ticket]:
        """Find an active ticket for the user.

        An active ticket is one with status NEW or IN_PROGRESS. This function is
        optimized to use a single query with JOIN instead of separate queries.
        """
        stmt = (
            select(Ticket)
            .join(Ticket.user)
            .options(contains_eager(Ticket.user), selectinload(Ticket.category))
            .where(
                User.external_id == user_id,
                User.source == source,
                Ticket.status.in_([TicketStatus.NEW, TicketStatus.IN_PROGRESS])
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_admin_message_id(self, message_id: int) -> Optional[Ticket]:
        """Find a ticket by the admin message ID in the staff chat."""
        stmt = (
            select(Ticket)
            .options(selectinload(Ticket.user)) # Load user immediately for replying
            .where(Ticket.admin_message_id == message_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history(self, user_id: int, limit: int = 3) -> List[Ticket]:
        """Get the user's ticket history."""
        stmt = (
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .order_by(desc(Ticket.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_next_daily_id(self) -> int:
        """Get the next daily_id atomically using a counter table."""
        today = datetime.date.today()

        # Try 1: Read with lock
        stmt = select(DailyTicketCounter).where(DailyTicketCounter.date == today).with_for_update()
        result = await self.session.execute(stmt)
        counter_row = result.scalar_one_or_none()

        if counter_row:
            counter_row.counter += 1
            await self.session.flush()
            return counter_row.counter

        # Try 2: Create
        try:
            async with self.session.begin_nested():
                new_counter = DailyTicketCounter(date=today, counter=1)
                self.session.add(new_counter)
                await self.session.flush()
            return 1
        except IntegrityError:
            # Race condition: someone else created it, retry read
            stmt = select(DailyTicketCounter).where(DailyTicketCounter.date == today).with_for_update()
            result = await self.session.execute(stmt)
            counter_row = result.scalar_one()
            counter_row.counter += 1
            await self.session.flush()
            return counter_row.counter
