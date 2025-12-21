import logging
import datetime
import html
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload, contains_eager
from database.models import Ticket, User, Message, TicketStatus, SourceType, SenderRole, Category
from core.config import settings
from core.constants import format_ticket_id
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

async def get_active_ticket(session: AsyncSession, user_id: int, source: str) -> Ticket | None:
    """Finds an active ticket for the user.
    
    Optimized to use a single query with JOIN instead of separate queries for User and Ticket.
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
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_user_history(session: AsyncSession, user_id: int) -> list[Ticket]:
    """Get last 3 tickets for history."""
    result = await session.execute(
        select(Ticket)
        .where(Ticket.user_id == user_id)
        .order_by(desc(Ticket.created_at))
        .limit(3)
    )
    return result.scalars().all()

async def create_ticket(session: AsyncSession, user_id: int, source: str, text: str, bot: Bot, category_name: str, user_full_name: str = "Unknown"):
    # 1. Find or create user
    result = await session.execute(select(User).where(User.external_id == user_id, User.source == source).limit(1))
    user = result.scalar_one_or_none()

    if not user:
        user = User(external_id=user_id, source=source, username="User", full_name=user_full_name)
        session.add(user)
        await session.flush()
    else:
        if user.full_name != user_full_name:
            user.full_name = user_full_name

    # 2. Get Category
    result = await session.execute(select(Category).where(Category.name == category_name).limit(1))
    category = result.scalar_one_or_none()
    if not category:
        # Fallback if category not found
        category = Category(name=category_name)
        session.add(category)
        await session.flush()

    # 3. Calculate daily_id
    today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Get the last ticket created today to increment its daily_id
    # This avoids counting all rows (O(N)) and uses the index (O(1))
    stmt = (
        select(Ticket.daily_id)
        .where(Ticket.created_at >= today_start)
        .order_by(desc(Ticket.created_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    last_daily_id = result.scalar_one_or_none()
    daily_id = (last_daily_id or 0) + 1
    
    # 4. Create Ticket
    active_ticket = Ticket(
        user_id=user.id,
        daily_id=daily_id,
        category_id=category.id,
        source=source,
        question_text=text, # Initial question text
        status=TicketStatus.NEW
    )
    session.add(active_ticket)
    await session.flush()

    # 5. Save first message
    msg = Message(ticket_id=active_ticket.id, sender_role=SenderRole.USER, text=text)
    session.add(msg)
    
    # 6. Get history for notification
    history = await get_user_history(session, user.id)
    history_text = ""
    for h in history:
        if h.id == active_ticket.id: continue # Skip current
        date_str = h.created_at.strftime("%d.%m.%Y")
        summary = h.summary or h.question_text[:30] + "..." if h.question_text else "No text"
        # Sanitize summary to prevent HTML injection from previous tickets
        safe_summary = html.escape(summary)
        history_text += f"- {date_str}: {safe_summary}\n"

    if not history_text:
        history_text = "Нет предыдущих обращений"

    # Commit DB changes
    await session.commit()

    # 7. Notify Staff/Admin
    try:
        # Create notification text
        category_text = category.name if category else "General"
        safe_user_name = html.escape(user_full_name)
        safe_text = html.escape(text)  # <--- SANITIZATION ADDED

        admin_text = (
            f"🔥 <b>Новый запрос №{active_ticket.daily_id}</b> ({format_ticket_id(active_ticket.id)})\n"
            f"От: <a href='tg://user?id={user_id}'>{safe_user_name}</a>\n"
            f"Тема: {category_text}\n"
            f"Текст: {safe_text}\n\n"
            f"<i>История:</i>\n{history_text}\n\n"
            f"<i>Ответьте на это сообщение (Reply), чтобы написать студенту.</i>"
        )

        # Add Close button
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"close_ticket_{active_ticket.id}")]
        ])

        # Notify staff chat
        await _send_staff_notification(bot, active_ticket, user, text, history_text, is_new_ticket=True)
    except Exception as e:
        logger.error(f"⚠️ Failed to notify staff: {e}")

    return active_ticket

async def add_message_to_ticket(session: AsyncSession, ticket: Ticket, text: str, bot: Bot):
    # Add message
    msg = Message(ticket_id=ticket.id, sender_role=SenderRole.USER, text=text)
    session.add(msg)
    await session.commit()

    # Notify Staff/Admin
    try:
        # Теперь это безопасно, так как мы подгрузили их в get_active_ticket
        user = ticket.user
        await _send_staff_notification(bot, ticket, user, text, is_new_ticket=False)
    except Exception as e:
        logger.error(f"⚠️ Failed to notify staff about new message: {e}")


async def _send_staff_notification(
    bot: Bot,
    ticket: Ticket,
    user: User,
    text: str,
    history_text: str = None,
    is_new_ticket: bool = False
):
    """
    Helper function to send notifications to staff.
    Handles message construction, HTML escaping, and truncation of long messages.
    """
    MAX_MESSAGE_LENGTH = 4096

    category_name = ticket.category.name if ticket.category else "General"
    category_text = html.escape(category_name)
    safe_user_name = html.escape(user.full_name or "Пользователь")

    # Prepare history part
    # Truncate raw history first if it's too long, to avoid slicing escaped entities later
    # 2000 chars of history is generous enough
    if history_text and len(history_text) > 2000:
        history_text = history_text[:2000] + "...(truncated)"

    # history_text is already HTML-escaped by the caller (create_ticket)
    safe_history = history_text if history_text else ""

    # Calculate metadata length (headers, footers, etc.)
    # We construct a dummy message without the variable text to measure overhead
    if is_new_ticket:
        dummy_header = f"🔥 <b>Новый запрос №{ticket.daily_id}</b> ({format_ticket_id(ticket.id)})"
        history_block = f"\n\n<i>История:</i>\n{safe_history}" if safe_history else ""
    else:
        dummy_header = f"📩 <b>Новое сообщение в тикете №{ticket.daily_id}</b> ({format_ticket_id(ticket.id)})"
        history_block = ""

    template_start = (
        f"{dummy_header}\n"
        f"От: <a href='tg://user?id={user.external_id}'>{safe_user_name}</a>\n"
        f"Тема: {category_text}\n"
        f"Текст: "
    )
    template_end = (
        f"{history_block}\n\n"
        f"<i>Ответьте на это сообщение (Reply), чтобы написать студенту.</i>"
    )

    metadata_len = len(template_start) + len(template_end)
    available_for_text = MAX_MESSAGE_LENGTH - metadata_len

    # Safety buffer
    available_for_text -= 100

    if available_for_text < 100:
        # If history is massive (should be rare due to pre-truncation), prioritize current text
        available_for_text = 2000

    # Truncate user text if necessary
    if len(text) > available_for_text:
        display_text = text[:available_for_text] + "... (truncated)"
    else:
        display_text = text

    safe_text = html.escape(display_text)

    admin_text = f"{template_start}{safe_text}{template_end}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"close_ticket_{ticket.id}")]
    ])

    # Final safety check
    # We trust our calculation above. If it's still too long, we let it fail (better than sending broken HTML)
    # or we could try to truncate intelligently again, but simple hard slice is dangerous for HTML.

    await bot.send_message(settings.TG_STAFF_CHAT_ID, admin_text, parse_mode="HTML", reply_markup=kb)
