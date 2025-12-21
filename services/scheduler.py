import logging
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func, and_
from database.setup import new_session
from database.models import Ticket, Category
from core.config import settings
from aiogram import Bot

logger = logging.getLogger(__name__)

async def send_daily_statistics(bot: Bot):
    """Send daily statistics report to admin.
    
    Collects and sends statistics about tickets created and closed today,
    including top categories by ticket count.
    
    Args:
        bot: The Bot instance for sending messages.
    """
    logger.info("Collecting daily statistics...")

    try:
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + datetime.timedelta(days=1)

        async with new_session() as session:
            # Total tickets today
            stmt_total = select(func.count(Ticket.id)).where(
                and_(Ticket.created_at >= today_start, Ticket.created_at < today_end)
            )
            total_requests = (await session.execute(stmt_total)).scalar() or 0

            # Total answered (Closed?) - Prompt says "Отвечено: M".
            # Assuming "Answered" means closed or admin replied?
            # Usually statistics mean Closed or maybe just tickets with Admin replies.
            # Let's count Closed tickets for now as "resolved/answered" proxy or checking messages.
            # But easier: Closed tickets today.
            # Or tickets created today that are closed?
            # Let's count tickets Closed today.

            stmt_closed = select(func.count(Ticket.id)).where(
                 and_(Ticket.closed_at >= today_start, Ticket.closed_at < today_end)
            )
            # OR: "Отвечено" might mean tickets where admin sent a message.
            # Let's stick to "Closed" or just "Total processed".
            # The example says "Отвечено: M". I'll assume Closed.
            closed_requests = (await session.execute(stmt_closed)).scalar() or 0

            # Top Categories
            stmt_cats = (
                select(Category.name, func.count(Ticket.id))
                .join(Ticket, Ticket.category_id == Category.id)
                .where(and_(Ticket.created_at >= today_start, Ticket.created_at < today_end))
                .group_by(Category.name)
                .order_by(func.count(Ticket.id).desc())
            )
            cat_results = (await session.execute(stmt_cats)).all()

        # Formatting report
        date_str = datetime.datetime.now().strftime("%d.%m.%Y")

        top_topics = ""
        for idx, (name, count) in enumerate(cat_results, 1):
            top_topics += f"{idx}. {name}: {count}\n"

        if not top_topics:
            top_topics = "Нет данных"

        report = (
            f"📊 <b>Статистика за {date_str}:</b>\n"
            f"Всего запросов: {total_requests}\n"
            f"Закрыто (Отвечено): {closed_requests}\n\n"
            f"<b>Топ тем:</b>\n"
            f"{top_topics}"
        )

        await bot.send_message(settings.TG_ADMIN_ID, report, parse_mode="HTML")
        logger.info("Daily statistics sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send daily statistics: {e}", exc_info=True)

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler()
    # Run at 23:59 every day
    scheduler.add_job(send_daily_statistics, 'cron', hour=23, minute=59, args=[bot])
    scheduler.start()
    return scheduler
