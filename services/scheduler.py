import logging
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func, and_
from database.setup import new_session
from database.models import Ticket, Category, TicketPriority
from core.config import settings
from aiogram import Bot

from database.repositories.ticket_repository import TicketRepository
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

async def send_daily_statistics(bot: Bot):
    """Send daily statistics report to admin.
    
    Collects and sends statistics about tickets created and closed today,
    including top categories by ticket count, priority distribution,
    average response time, and student satisfaction ratings.
    
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

            # Total closed today
            stmt_closed = select(func.count(Ticket.id)).where(
                 and_(Ticket.closed_at >= today_start, Ticket.closed_at < today_end)
            )
            closed_requests = (await session.execute(stmt_closed)).scalar() or 0
            
            # Priority distribution
            priority_stats = {}
            for priority in TicketPriority:
                stmt_priority = select(func.count(Ticket.id)).where(
                    and_(
                        Ticket.created_at >= today_start,
                        Ticket.created_at < today_end,
                        Ticket.priority == priority
                    )
                )
                count = (await session.execute(stmt_priority)).scalar() or 0
                if count > 0:
                    priority_stats[priority.value] = count
            
            # Average response time (in minutes)
            stmt_avg_response = select(
                func.avg(
                    func.julianday(Ticket.first_response_at) - func.julianday(Ticket.created_at)
                ) * 24 * 60  # Convert days to minutes
            ).where(
                and_(
                    Ticket.created_at >= today_start,
                    Ticket.created_at < today_end,
                    Ticket.first_response_at.isnot(None)
                )
            )
            avg_response_minutes = (await session.execute(stmt_avg_response)).scalar()
            
            # Average satisfaction rating
            stmt_avg_rating = select(func.avg(Ticket.rating)).where(
                and_(
                    Ticket.closed_at >= today_start,
                    Ticket.closed_at < today_end,
                    Ticket.rating.isnot(None)
                )
            )
            avg_rating = (await session.execute(stmt_avg_rating)).scalar()
            
            # Count of rated tickets
            stmt_rated = select(func.count(Ticket.id)).where(
                and_(
                    Ticket.closed_at >= today_start,
                    Ticket.closed_at < today_end,
                    Ticket.rating.isnot(None)
                )
            )
            rated_count = (await session.execute(stmt_rated)).scalar() or 0

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
        
        # Priority breakdown
        priority_text = ""
        priority_names = {
            "urgent": "🔴 Срочно",
            "high": "🟠 Высокий",
            "normal": "🟢 Обычный",
            "low": "⚪ Низкий"
        }
        for priority, count in priority_stats.items():
            priority_text += f"{priority_names.get(priority, priority)}: {count}\n"
        
        if not priority_text:
            priority_text = "Нет данных"
        
        # Response time
        response_time_text = "Нет данных"
        if avg_response_minutes is not None:
            if avg_response_minutes < 60:
                response_time_text = f"{int(avg_response_minutes)} мин"
            else:
                hours = avg_response_minutes / 60
                response_time_text = f"{hours:.1f} ч"
        
        # Rating
        rating_text = "Нет данных"
        if avg_rating is not None and rated_count > 0:
            stars = "⭐" * round(avg_rating)
            rating_text = f"{avg_rating:.1f}/5 {stars} ({rated_count} оценок)"

        report = (
            f"📊 <b>Статистика за {date_str}:</b>\n\n"
            f"<b>Общее:</b>\n"
            f"Всего запросов: {total_requests}\n"
            f"Закрыто: {closed_requests}\n\n"
            f"<b>По приоритетам:</b>\n"
            f"{priority_text}\n"
            f"<b>Топ тем:</b>\n"
            f"{top_topics}\n"
            f"<b>SLA метрики:</b>\n"
            f"Среднее время ответа: {response_time_text}\n"
            f"Средняя оценка: {rating_text}"
        )

        await bot.send_message(settings.TG_ADMIN_ID, report, parse_mode="HTML")
        logger.info("Daily statistics sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send daily statistics: {e}", exc_info=True)

async def send_weekly_faq_analysis(bot: Bot):
    """Weekly analysis of trends and FAQ suggestions."""
    logger.info("Starting weekly FAQ analysis...")

    try:
        # 1. Define period (last 7 days)
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)

        async with new_session() as session:
            repo = TicketRepository(session)
            # 2. Get raw data
            summaries = await repo.get_closed_summaries_since(week_ago)

            if len(summaries) < 5:
                # If few tickets, analysis is not meaningful
                return

            # 3. Analyze via LLM
            report = await LLMService.suggest_faq_updates(summaries)

        # 4. Send report to Admin
        msg = (
            f"🧠 <b>Еженедельный AI-анализ поддержки</b>\n"
            f"Проанализировано тикетов: {len(summaries)}\n\n"
            f"{report}\n\n"
            f"<i>Чтобы добавить FAQ, просто скопируйте и отправьте команду из отчета.</i>"
        )

        await bot.send_message(settings.TG_ADMIN_ID, msg, parse_mode="HTML")
        logger.info("Weekly FAQ analysis sent.")

    except Exception as e:
        logger.error(f"Failed weekly analysis: {e}", exc_info=True)

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler()

    # Send statistics every day at 23:59
    scheduler.add_job(send_daily_statistics, 'cron', hour=23, minute=59, args=[bot])

    # Weekly analysis (Sunday, 20:00)
    scheduler.add_job(send_weekly_faq_analysis, 'cron', day_of_week='sun', hour=20, minute=0, args=[bot])

    scheduler.start()
    return scheduler
