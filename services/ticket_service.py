import logging
import datetime
import html
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload  # <--- 1. ВАЖНЫЙ ИМПОРТ
from database.models import Ticket, User, Message, TicketStatus, SourceType, SenderRole, Category
from core.config import settings
from core.constants import format_ticket_id
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

async def get_active_ticket(session: AsyncSession, user_id: int, source: str) -> Ticket | None:
    """Finds an active ticket for the user."""
    # 1. Get user
    result = await session.execute(select(User).where(User.external_id == user_id, User.source == source).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    # 2. Find active ticket
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: Добавляем options(selectinload(...)) ---
    # Это сразу загрузит User и Category, чтобы не было ошибки при отправке уведомления
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.user), selectinload(Ticket.category))
        .where(
            Ticket.user_id == user.id, 
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

    # Count tickets created today
    stmt = select(func.count(Ticket.id)).where(Ticket.created_at >= today_start)
    count_result = await session.execute(stmt)
    today_count = count_result.scalar() or 0
    daily_id = today_count + 1
    
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
        history_text += f"- {date_str}: {summary}\n"

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
        await bot.send_message(settings.TG_STAFF_CHAT_ID, admin_text, parse_mode="HTML", reply_markup=kb)
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
        category = ticket.category
        safe_user_name = html.escape(user.full_name or "Пользователь")
        safe_text = html.escape(text) # <--- SANITIZATION ADDED

        admin_text = (
            f"📩 <b>Новое сообщение в тикете №{ticket.daily_id}</b> ({format_ticket_id(ticket.id)})\n"
            f"От: <a href='tg://user?id={user.external_id}'>{safe_user_name}</a>\n"
            f"Тема: {category.name if category else 'General'}\n"
            f"Текст: {safe_text}\n\n"
            f"<i>Ответьте на это сообщение (Reply), чтобы написать студенту.</i>"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"close_ticket_{ticket.id}")]
        ])
                
        # Notify staff chat
        await bot.send_message(settings.TG_STAFF_CHAT_ID, admin_text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"⚠️ Failed to notify staff about new message: {e}")
