import logging
import datetime
import html
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from sqlalchemy.orm import selectinload, contains_eager
from database.models import Ticket, User, Message, TicketStatus, SourceType, SenderRole, Category, TicketPriority
from database.repositories.ticket_repository import TicketRepository
from core.config import settings
from core.constants import format_ticket_id
from services.priority_service import detect_priority, get_priority_emoji, get_priority_text
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message as TgMessage

logger = logging.getLogger(__name__)

async def get_next_daily_id(session: AsyncSession) -> int:
    """Get the next daily_id atomically using a counter table.
    
    Delegates to TicketRepository.
    """
    repo = TicketRepository(session)
    return await repo.get_next_daily_id()


async def get_active_ticket(session: AsyncSession, user_id: int, source: str) -> Ticket | None:
    """Find an active ticket for the user.
    
    Delegates to TicketRepository.
    """
    repo = TicketRepository(session)
    return await repo.get_active_by_user(user_id, source)

async def get_user_history(session: AsyncSession, user_id: int) -> list[Ticket]:
    """Get the last 3 tickets for a user's history.
    
    Delegates to TicketRepository.
    """
    repo = TicketRepository(session)
    return await repo.get_history(user_id)

async def create_ticket(
    session: AsyncSession,
    user_id: int,
    source: str,
    text: str,
    bot: Bot,
    category_name: str,
    user_full_name: str = "Unknown",
    media_id: str = None,
    content_type: str = "text"
) -> Ticket:
    """Create a new ticket for a user.
    
    Args:
        session: Database session
        user_id: External user ID (Telegram ID)
        source: Source platform ('tg' or 'vk')
        text: Question text (optional if media provided)
        bot: Bot instance for notifications
        category_name: Category name for the ticket
        user_full_name: User's full name (default: "Unknown")
        media_id: File ID for photo/document
        content_type: Type of content ('text', 'photo', 'document')
        
    Returns:
        The created Ticket object
        
    Raises:
        ValueError: If text is empty (and no media) or too long
    """
    # Validate inputs
    text = text.strip() if text else ""

    if not text and not media_id:
        raise ValueError("Question text cannot be empty unless sending media")
    
    if len(text) > 10000:  # Reasonable limit for ticket text
        raise ValueError("Question text is too long (max 10000 characters)")
    
    # Initialize Repo
    repo = TicketRepository(session)

    # 1. Find or create user
    # (Leaving raw SQL for User here as instructed to focus on Ticket logic,
    # but could be moved to UserRepository in future)
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

    # 3. Get next daily_id atomically via Repo
    daily_id = await repo.get_next_daily_id()
    
    # 3.5. Detect priority automatically (only if text is present)
    priority = detect_priority(text, category_name) if text else TicketPriority.NORMAL
    
    # 4. Create Ticket
    active_ticket = Ticket(
        user_id=user.id,
        daily_id=daily_id,
        category_id=category.id,
        source=source,
        question_text=text if text else "[Вложение]", # Initial question text or placeholder
        status=TicketStatus.NEW,
        priority=priority
    )
    session.add(active_ticket)
    await session.flush()

    # 5. Save first message
    msg = Message(
        ticket_id=active_ticket.id,
        sender_role=SenderRole.USER,
        text=text,
        media_id=media_id,
        content_type=content_type
    )
    session.add(msg)
    
    # 6. Get history for notification via Repo
    history = await repo.get_history(user.id)
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

    # 7. Notify Staff/Admin and Save Message ID
    try:
        sent_msg = await _send_staff_notification(
            bot, active_ticket, user, text, history_text, is_new_ticket=True,
            media_id=media_id, content_type=content_type
        )

        if sent_msg:
            active_ticket.admin_message_id = sent_msg.message_id
            await session.commit() # Save the link "Ticket <-> Staff Chat Message"

    except Exception as e:
        logger.error(f"⚠️ Failed to notify staff: {e}")

    return active_ticket

async def add_message_to_ticket(
    session: AsyncSession,
    ticket: Ticket,
    text: str,
    bot: Bot,
    media_id: str = None,
    content_type: str = "text"
) -> None:
    """Add a user message to an existing ticket and notify staff.
    
    This function adds a new message from the user to the ticket's message
    history and sends a notification to the staff chat.
    
    If ticket was closed, it re-opens it.

    Args:
        session: Database session
        ticket: The ticket to add the message to (must have user and category loaded)
        text: The message text from the user
        bot: Bot instance for sending notifications
        media_id: File ID if present
        content_type: Type of content
        
    Note:
        The ticket object must have its user and category relationships
        pre-loaded (via selectinload) to avoid lazy-loading issues.
    """
    # Re-open if closed
    if ticket.status == TicketStatus.CLOSED:
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.closed_at = None
        # Could log re-opening here

    # Add message
    msg = Message(
        ticket_id=ticket.id,
        sender_role=SenderRole.USER,
        text=text,
        media_id=media_id,
        content_type=content_type
    )
    session.add(msg)
    await session.commit()

    # Notify Staff/Admin
    try:
        # Теперь это безопасно, так как мы подгрузили их в get_active_ticket
        user = ticket.user
        sent_msg = await _send_staff_notification(
            bot, ticket, user, text, is_new_ticket=False,
            media_id=media_id, content_type=content_type
        )

        if sent_msg:
            # Update admin_message_id so staff can reply to the latest message
            ticket.admin_message_id = sent_msg.message_id
            await session.commit()

    except Exception as e:
        logger.error(f"⚠️ Failed to notify staff about new message: {e}")


async def _send_staff_notification(
    bot: Bot,
    ticket: Ticket,
    user: User,
    text: str,
    history_text: str = None,
    is_new_ticket: bool = False,
    media_id: str = None,
    content_type: str = "text"
) -> Optional[TgMessage]:
    """
    Helper function to send notifications to staff.
    Handles message construction, HTML escaping, and truncation of long messages.
    Supports media attachments (photo/document).
    Returns the sent Message object or None.
    """
    MAX_MESSAGE_LENGTH = 1024 if media_id else 4096 # Caption limit is 1024

    category_name = ticket.category.name if ticket.category else "General"
    category_text = html.escape(category_name)
    safe_user_name = html.escape(user.full_name or "Пользователь")

    # Prepare history part
    # Truncate raw history first if it's too long
    if history_text and len(history_text) > 2000:
        history_text = history_text[:2000] + "...(truncated)"

    safe_history = history_text if history_text else ""

    # Calculate metadata length
    priority_emoji = get_priority_emoji(ticket.priority)
    priority_text = get_priority_text(ticket.priority)
    
    # Add student info if available
    student_info = ""
    if user.student_id or user.department or user.course:
        parts = []
        if user.student_id:
            parts.append(f"ID: {user.student_id}")
        if user.course:
            parts.append(f"{user.course} курс")
        if user.department:
            parts.append(html.escape(user.department))
        student_info = f"\n🎓 {', '.join(parts)}"
    
    if is_new_ticket:
        dummy_header = f"{priority_emoji} <b>Новый запрос №{ticket.daily_id}</b> ({format_ticket_id(ticket.id)})"
        history_block = f"\n\n<i>История:</i>\n{safe_history}" if safe_history else ""
    else:
        dummy_header = f"📩 <b>Новое сообщение в тикете №{ticket.daily_id}</b> ({format_ticket_id(ticket.id)})"
        history_block = ""

    template_start = (
        f"{dummy_header}\n"
        f"От: <a href='tg://user?id={user.external_id}'>{safe_user_name}</a>{student_info}\n"
        f"Тема: {category_text} | Приоритет: {priority_text}\n"
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
        available_for_text = 500 # Ensure at least some text space if caption allows

    # Handle text being None (media only)
    display_text = text if text else ""

    # Truncate user text if necessary
    if len(display_text) > available_for_text:
        display_text = display_text[:available_for_text] + "... (truncated)"

    safe_text = html.escape(display_text)

    if not display_text and media_id:
        safe_text = "<i>(Вложение)</i>"

    admin_text = f"{template_start}{safe_text}{template_end}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"close_ticket_{ticket.id}")]
    ])

    try:
        if content_type == "photo" and media_id:
            return await bot.send_photo(
                settings.TG_STAFF_CHAT_ID,
                photo=media_id,
                caption=admin_text,
                parse_mode="HTML",
                reply_markup=kb
            )
        elif content_type == "document" and media_id:
            return await bot.send_document(
                settings.TG_STAFF_CHAT_ID,
                document=media_id,
                caption=admin_text,
                parse_mode="HTML",
                reply_markup=kb
            )
        else:
            return await bot.send_message(
                settings.TG_STAFF_CHAT_ID,
                admin_text,
                parse_mode="HTML",
                reply_markup=kb
            )
    except Exception as e:
        logger.error(f"⚠️ Failed to notify staff: {e}")
        return None
