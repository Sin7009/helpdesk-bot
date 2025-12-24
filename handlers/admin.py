import re
import html
import logging
import csv
import io
import datetime
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from database.setup import new_session
from database.models import User, UserRole, FAQ, Ticket, TicketStatus, Message, SenderRole, Category
from database.repositories.ticket_repository import TicketRepository
from core.config import settings
from core.constants import TICKET_ID_PATTERN
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = Router()

# --- ПРОВЕРКА ПРАВ ---
async def is_admin_or_mod(user_id: int, session: AsyncSession) -> bool:
    """Check if user is an admin or moderator.
    
    Args:
        user_id: Telegram user ID
        session: Database session
        
    Returns:
        True if user is admin or moderator, False otherwise
    """
    if user_id == settings.TG_ADMIN_ID:
        return True
    stmt = select(User).where(User.external_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    return user and user.role in [UserRole.ADMIN, UserRole.MODERATOR]

async def is_root_admin(user_id: int) -> bool:
    """Check if user is the root admin.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if user is the root admin
    """
    return user_id == settings.TG_ADMIN_ID


def _get_rating_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Create rating keyboard for closed ticket.
    
    Args:
        ticket_id: ID of the ticket
        
    Returns:
        InlineKeyboardMarkup with rating buttons
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data=f"rate_{ticket_id}_1"),
            InlineKeyboardButton(text="⭐⭐", callback_data=f"rate_{ticket_id}_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate_{ticket_id}_3")
        ],
        [
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"rate_{ticket_id}_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate_{ticket_id}_5")
        ]
    ])


async def _close_ticket_with_summary(
    session: AsyncSession,
    ticket: Ticket,
    bot: Bot
) -> bool:
    """Close a ticket, generate summary and notify user.
    
    This helper function consolidates the ticket closing logic:
    1. Generates AI summary from messages
    2. Sets ticket status to CLOSED
    3. Sends rating request to user
    
    Args:
        session: Database session
        ticket: Ticket object (must have user relationship loaded)
        bot: Bot instance for notifications
        
    Returns:
        True if ticket was closed successfully, False otherwise
    """
    if ticket.status == TicketStatus.CLOSED:
        return False
    
    # 1. Generate summary before closing (if messages exist)
    msgs_stmt = select(Message).where(Message.ticket_id == ticket.id).order_by(Message.created_at)
    msgs_result = await session.execute(msgs_stmt)
    messages_list = msgs_result.scalars().all()
    
    if messages_list:
        dialogue_text = LLMService.format_dialogue(messages_list)
        summary = await LLMService.generate_summary(dialogue_text)
        ticket.summary = summary
        logger.info(f"Generated summary for ticket #{ticket.id}: {summary}")
    
    # 2. Close the ticket
    ticket.status = TicketStatus.CLOSED
    ticket.closed_at = func.now()
    await session.commit()
    
    # 3. Notify user with rating request
    try:
        await bot.send_message(
            ticket.user.external_id,
            "✅ <b>Ваш вопрос решен. Диалог закрыт.</b>\n\n"
            "Пожалуйста, оцените качество помощи:",
            parse_mode="HTML",
            reply_markup=_get_rating_keyboard(ticket.id)
        )
    except Exception as e:
        logger.warning(f"Failed to send rating request to user {ticket.user.external_id}: {e}")
    
    return True


# --- УПРАВЛЕНИЕ (Модераторы / FAQ / Категории) ---

# НОВОЕ: Обработчик команды /admin
@router.message(Command("admin"))
async def open_admin_panel_cmd(message: types.Message, session: AsyncSession):
    """Открыть WebApp админ-панель."""
    if not await is_admin_or_mod(message.from_user.id, session):
        return

    # Проверка наличия URL в конфиге
    if not settings.WEBAPP_URL:
        await message.answer("❌ Ошибка: в .env не указан WEBAPP_URL")
        return

    # Формируем URL для кнопки
    base_url = settings.WEBAPP_URL.rstrip('/')
    admin_url = f"{base_url}/webapp/admin"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📱 Открыть панель",
                web_app=types.WebAppInfo(url=admin_url)
            )
        ]
    ])

    await message.answer(
        "<b>Панель управления тикетами</b>\n"
        "Нажмите кнопку ниже, чтобы открыть список заявок и статистику.",
        parse_mode="HTML",
        reply_markup=markup
    )

@router.message(Command("add_category"))
async def add_category_cmd(message: types.Message, command: CommandObject):
    async with new_session() as session:
        if not await is_admin_or_mod(message.from_user.id, session): return
        from database.models import Category
        try:
            if not command.args:
                 await message.answer("Ошибка: введите название категории")
                 return
            name = command.args.strip()
            session.add(Category(name=name))
            await session.commit()
            await message.answer(f"✅ Категория '{name}' добавлена.")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")


# --- НАЗНАЧЕНИЕ ТИКЕТОВ ---

@router.message(Command("assign"))
async def assign_ticket_cmd(message: types.Message, command: CommandObject, session: AsyncSession):
    """Assign a ticket to a staff member.
    
    Usage: /assign <ticket_id> @username
    
    Args:
        message: The message containing the command
        command: CommandObject with parsed arguments
        session: Database session
    """
    if not await is_admin_or_mod(message.from_user.id, session):
        return
    
    if not command.args:
        await message.answer(
            "📋 <b>Формат:</b> /assign &lt;ticket_id&gt; @username\n\n"
            "Пример: /assign 123 @moderator",
            parse_mode="HTML"
        )
        return
    
    # Parse arguments
    parts = command.args.strip().split()
    if len(parts) < 2:
        await message.answer(
            "❌ Недостаточно аргументов.\n"
            "Формат: /assign &lt;ticket_id&gt; @username",
            parse_mode="HTML"
        )
        return
    
    try:
        ticket_id = int(parts[0])
    except ValueError:
        await message.answer("❌ ID тикета должен быть числом.")
        return
    
    # Extract username (remove @ if present)
    username = parts[1].lstrip("@").strip()
    
    if not username:
        await message.answer("❌ Укажите username сотрудника.")
        return
    
    # Find the ticket
    stmt = select(Ticket).options(
        selectinload(Ticket.user),
        selectinload(Ticket.assigned_staff)
    ).where(Ticket.id == ticket_id)
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        await message.answer(f"❌ Тикет #{ticket_id} не найден.")
        return
    
    if ticket.status == TicketStatus.CLOSED:
        await message.answer(f"❌ Тикет #{ticket_id} уже закрыт.")
        return
    
    # Find the staff member by username
    stmt = select(User).where(
        User.username == username,
        User.role.in_([UserRole.ADMIN, UserRole.MODERATOR])
    )
    result = await session.execute(stmt)
    staff = result.scalar_one_or_none()
    
    if not staff:
        await message.answer(
            f"❌ Пользователь @{html.escape(username)} не найден "
            "или не является модератором/администратором."
        )
        return
    
    # Assign the ticket
    old_assignee = ticket.assigned_staff.username if ticket.assigned_staff else None
    ticket.assigned_to = staff.id
    
    # Change status to IN_PROGRESS if it was NEW
    if ticket.status == TicketStatus.NEW:
        ticket.status = TicketStatus.IN_PROGRESS
    
    await session.commit()
    
    # Notify
    if old_assignee:
        await message.answer(
            f"✅ Тикет #{ticket_id} переназначен с @{html.escape(old_assignee)} "
            f"на @{html.escape(username)}."
        )
    else:
        await message.answer(
            f"✅ Тикет #{ticket_id} назначен на @{html.escape(username)}."
        )


# --- ЭКСПОРТ СТАТИСТИКИ В CSV ---

@router.message(Command("export"))
async def export_statistics_cmd(message: types.Message, command: CommandObject, session: AsyncSession):
    """Export ticket statistics to CSV file.
    
    Usage: /export [days]
    Default: last 30 days
    
    Args:
        message: The message containing the command
        command: CommandObject with parsed arguments
        session: Database session
    """
    if not await is_admin_or_mod(message.from_user.id, session):
        return
    
    # Parse days argument (default 30)
    days = 30
    if command.args:
        try:
            days = int(command.args.strip())
            if days < 1 or days > 365:
                await message.answer("❌ Количество дней должно быть от 1 до 365.")
                return
        except ValueError:
            await message.answer("❌ Укажите число дней. Пример: /export 7")
            return
    
    await message.answer(f"📊 Генерирую отчет за {days} дней...")
    
    # Calculate date range
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)
    
    # Fetch tickets
    stmt = (
        select(Ticket)
        .options(
            selectinload(Ticket.user),
            selectinload(Ticket.category),
            selectinload(Ticket.assigned_staff)
        )
        .where(Ticket.created_at >= start_date)
        .order_by(Ticket.created_at.desc())
    )
    result = await session.execute(stmt)
    tickets = result.scalars().all()
    
    if not tickets:
        await message.answer("📭 Нет тикетов за указанный период.")
        return
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID",
        "Daily ID",
        "Дата создания",
        "Дата закрытия",
        "Статус",
        "Приоритет",
        "Категория",
        "Пользователь",
        "User ID",
        "Назначен на",
        "Время первого ответа (мин)",
        "Оценка",
        "Текст вопроса"
    ])
    
    # Data rows
    for ticket in tickets:
        # Calculate first response time in minutes
        first_response_mins = None
        if ticket.first_response_at and ticket.created_at:
            delta = ticket.first_response_at - ticket.created_at
            first_response_mins = round(delta.total_seconds() / 60, 1)
        
        # Prepare content and sanitize for CSV Injection
        q_text = (ticket.question_text[:100] + "...") if ticket.question_text and len(ticket.question_text) > 100 else (ticket.question_text or "")

        # Sanitize text to prevent CSV Injection (starting with =, +, -, @)
        if q_text and q_text.strip().startswith(('=', '+', '-', '@')):
            q_text = "'" + q_text

        # Also sanitize user name just in case
        u_name = ticket.user.full_name if ticket.user else ""
        if u_name and u_name.strip().startswith(('=', '+', '-', '@')):
            u_name = "'" + u_name

        writer.writerow([
            ticket.id,
            ticket.daily_id,
            ticket.created_at.strftime("%Y-%m-%d %H:%M") if ticket.created_at else "",
            ticket.closed_at.strftime("%Y-%m-%d %H:%M") if ticket.closed_at else "",
            ticket.status.value if ticket.status else "",
            ticket.priority.value if ticket.priority else "",
            ticket.category.name if ticket.category else "",
            u_name,
            ticket.user.external_id if ticket.user else "",
            ticket.assigned_staff.username if ticket.assigned_staff else "",
            first_response_mins if first_response_mins else "",
            ticket.rating if ticket.rating else "",
            q_text
        ])
    
    # Prepare file
    csv_content = output.getvalue()
    output.close()
    
    # Send file
    filename = f"tickets_export_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    file = BufferedInputFile(
        csv_content.encode('utf-8-sig'),  # BOM for Excel compatibility
        filename=filename
    )
    
    await message.answer_document(
        file,
        caption=f"📊 Экспорт тикетов за {days} дней\n"
                f"Всего: {len(tickets)} записей"
    )


# --- ОБРАБОТКА ОТВЕТОВ (Диалог) ---

# 1. Ответ СВАЙПОМ (Native Reply)
@router.message(F.reply_to_message)
async def admin_reply_native(message: types.Message, bot: Bot, session: AsyncSession):
    """Handle admin replies via native Telegram reply.
    
    Args:
        message: The reply message from admin
        bot: Bot instance
        session: Database session
    """
    # 1. Проверка прав
    if not await is_admin_or_mod(message.from_user.id, session):
        return

    # 2. Проверка: отвечаем ли мы боту?
    bot_obj = await bot.get_me()
    if message.reply_to_message.from_user.id != bot_obj.id:
        return

    # Инициализируем репозиторий
    ticket_repo = TicketRepository(session)

    # 3. Парсинг / Поиск тикета
    
    # 3.1 Поиск по ID сообщения (Ironclad method)
    reply_msg_id = message.reply_to_message.message_id
    ticket = await ticket_repo.get_by_admin_message_id(reply_msg_id)
    
    # 3.2 Если не нашли (старый тикет) — включаем Fallback (Regex)
    if not ticket:
        origin_text = message.reply_to_message.text or message.reply_to_message.caption or ""

        # Ищем ID: #123 (Основной формат)
        match = re.search(r"ID:\s*#(\d+)", origin_text)

        # Fallback (Если вдруг старый формат #123)
        if not match:
            match = re.search(r"#(\d+)", origin_text)

        if match:
            try:
                ticket_id = int(match.group(1))
                # Validate ticket_id is reasonable
                if 0 < ticket_id < 2147483647:
                    # Manually fetch ticket if found via regex since repo doesn't have get_by_id logic exposed easily
                    # or we can use generic get_by_id from BaseRepo if public, but it doesn't load User.
                    # So we use manual query to be safe and match process_reply expectation.
                    stmt = select(Ticket).options(selectinload(Ticket.user)).where(Ticket.id == ticket_id)
                    result = await session.execute(stmt)
                    ticket = result.scalar_one_or_none()
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse ticket ID from text: {origin_text}, error: {e}")

    if not ticket:
        # Если не нашли ID тикета — просто игнорируем
        return

    # 4. Extract content (text, photo, document)
    text = message.text or message.caption or ""
    media_id = None
    content_type = "text"

    if message.photo:
        content_type = "photo"
        media_id = message.photo[-1].file_id # Best quality
    elif message.document:
        content_type = "document"
        media_id = message.document.file_id

    if content_type == "text" and (not text or not text.strip()):
        await message.answer("⚠️ Текст ответа не может быть пустым.")
        return

    await process_reply(
        bot, session, ticket.id, text, message,
        close=False, ticket_obj=ticket,
        media_id=media_id, content_type=content_type
    )

# 2. Команда /reply ID Текст
@router.message(Command("reply"))
async def admin_reply_command(message: types.Message, command: CommandObject, bot: Bot):
    async with new_session() as session:
        if not await is_admin_or_mod(message.from_user.id, session): return
        if not command.args:
             await message.answer("Формат: /reply ID Текст")
             return
        try:
            t_id, text = command.args.split(" ", 1)
            # For command, we don't have the object, so we pass ID
            await process_reply(bot, session, int(t_id), text, message, close=False)
        except ValueError:
            await message.answer("Формат: /reply ID Текст")
        except Exception as e:
             await message.answer(f"Ошибка: {e}")


# 3. Команда /close ID (Закрыть тикет принудительно)
@router.message(Command("close"))
async def admin_close_ticket(message: types.Message, command: CommandObject, bot: Bot, session: AsyncSession):
    if not await is_admin_or_mod(message.from_user.id, session): return
    if not command.args:
        await message.answer("Формат: /close ID")
        return
    try:
        t_id = int(command.args.strip())
        # Use selectinload to fetch user eagerly for notification
        stmt = select(Ticket).options(selectinload(Ticket.user)).where(Ticket.id == t_id)
        result = await session.execute(stmt)
        ticket = result.scalar_one_or_none()

        if ticket:
            closed = await _close_ticket_with_summary(session, ticket, bot)
            if closed:
                await message.answer(f"Тикет #{t_id} закрыт.")
            else:
                await message.answer("Тикет уже закрыт.")
        else:
            await message.answer("Тикет не найден.")
    except ValueError:
        await message.answer("Формат: /close ID")
            
@router.callback_query(F.data.startswith("close_"))
async def close_ticket_btn(callback: types.CallbackQuery, bot: Bot):
    async with new_session() as session:
        if not await is_admin_or_mod(callback.from_user.id, session):
            await callback.answer("У вас нет прав.", show_alert=True)
            return

        t_id = int(callback.data.split("_")[-1])
        # Use selectinload to fetch user eagerly for notification
        stmt = select(Ticket).options(selectinload(Ticket.user)).where(Ticket.id == t_id)
        result = await session.execute(stmt)
        ticket = result.scalar_one_or_none()
        
        if ticket:
            closed = await _close_ticket_with_summary(session, ticket, bot)
            if closed:
                # Экранируем текст сообщения перед редактированием, так как используем parse_mode="HTML"
                # и callback.message.text возвращает простой текст, который может содержать спецсимволы (<, >)
                original_text = callback.message.text

                if original_text:
                    safe_text = html.escape(original_text)
                    await callback.message.edit_text(f"{safe_text}\n\n✅ <b>ЗАКРЫТО</b>", parse_mode="HTML")
                elif callback.message.caption:
                    # Если это медиа с подписью, мы не можем превратить его в текст через edit_text
                    # Лучше просто удалить кнопки (edit_reply_markup) и отправить новое сообщение
                    await callback.message.edit_reply_markup(reply_markup=None)
                    await callback.message.reply("✅ <b>Тикет закрыт.</b>", parse_mode="HTML")
                else:
                    # Если ничего нет (странно), просто пишем ответ
                    await callback.message.answer("✅ <b>Тикет закрыт.</b>", parse_mode="HTML")
                    try:
                        await callback.message.edit_reply_markup(reply_markup=None)
                    except Exception as e:
                        logger.warning(f"Failed to edit reply markup: {e}")
            else:
                await callback.answer("Тикет уже закрыт.")
        else:
            await callback.answer("Тикет не найден.")

async def process_reply(
    bot: Bot,
    session: AsyncSession,
    ticket_id: int,
    text: str,
    message: types.Message,
    close: bool = False,
    ticket_obj: Ticket | None = None,
    media_id: str = None,
    content_type: str = "text"
) -> None:
    """Process admin reply to a ticket.
    
    Args:
        bot: Bot instance
        session: Database session
        ticket_id: ID of the ticket to reply to
        text: Reply text
        message: Admin's message object
        close: Whether to close the ticket after replying
        ticket_obj: Optional Ticket object if already loaded
        media_id: Optional file ID
        content_type: Content type
    """
    text = text.strip() if text else ""

    if content_type == "text" and not text:
        await message.answer("⚠️ Текст ответа не может быть пустым.")
        return
    
    ticket = ticket_obj
    if not ticket:
        # Используем stmt вместо get, чтобы подгрузить User сразу
        stmt = select(Ticket).options(selectinload(Ticket.user)).where(Ticket.id == ticket_id)
        result = await session.execute(stmt)
        ticket = result.scalar_one_or_none()

    if not ticket:
        await message.answer("❌ Тикет не найден.")
        return
    
    if ticket.status == TicketStatus.CLOSED:
        await message.answer("⚠️ Этот тикет уже закрыт.")
        return

    user = ticket.user  # Теперь это безопасно, данные уже в памяти
    
    # Отправляем студенту
    try:
        # 🎨 Palette UX: Добавляем подсказку, как ответить
        reply_hint = "\n\n<i>(Чтобы ответить, просто отправьте сообщение)</i>" if not close else ""

        # FIX: Sanitize admin text to prevent HTML injection
        safe_text = html.escape(text)
        reply_text = f"👨‍💼 <b>Ответ:</b>\n{safe_text}{reply_hint}"

        if content_type == "photo" and media_id:
            await bot.send_photo(
                user.external_id,
                photo=media_id,
                caption=reply_text,
                parse_mode="HTML"
            )
        elif content_type == "document" and media_id:
            await bot.send_document(
                user.external_id,
                document=media_id,
                caption=reply_text,
                parse_mode="HTML"
            )
        else:
             await bot.send_message(
                user.external_id,
                reply_text,
                parse_mode="HTML"
            )
        
        # Сохраняем ответ Админа в историю переписки
        msg = Message(
            ticket_id=ticket.id,
            sender_role=SenderRole.ADMIN,
            text=text,
            media_id=media_id,
            content_type=content_type
        )
        session.add(msg)
        
        # Track first response time (SLA metric)
        if ticket.first_response_at is None:
            ticket.first_response_at = func.now()
        
        status_msg = "Ответ отправлен."
        if close:
            ticket.status = TicketStatus.CLOSED
            ticket.closed_at = func.now()
            status_msg += " Тикет закрыт."
        else:
            # Если не закрываем — меняем статус на In Progress, чтобы студент мог писать дальше
            if ticket.status == TicketStatus.NEW:
                ticket.status = TicketStatus.IN_PROGRESS
        
        await session.commit()
        await message.react([types.ReactionTypeEmoji(emoji="👍")])  # Ставим лайк сообщению админа вместо спама текстом
    except Exception as e:
        logger.error(f"Failed to send reply to user {user.external_id}: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка отправки: {e}")

# --- RATING HANDLER (Student satisfaction) ---

@router.callback_query(F.data.startswith("rate_"))
async def handle_rating(callback: types.CallbackQuery, bot: Bot):
    """Handle student satisfaction rating for closed tickets."""
    async with new_session() as session:
        try:
            # Parse callback data: rate_{ticket_id}_{rating}
            parts = callback.data.split("_")
            if len(parts) != 3:
                await callback.answer("❌ Ошибка формата данных")
                return
            
            ticket_id = int(parts[1])
            rating = int(parts[2])
            
            if rating < 1 or rating > 5:
                await callback.answer("❌ Неверная оценка")
                return
            
            # Get ticket with user and category eagerly loaded
            stmt = select(Ticket).options(
                selectinload(Ticket.user),
                selectinload(Ticket.category)
            ).where(Ticket.id == ticket_id)
            result = await session.execute(stmt)
            ticket = result.scalar_one_or_none()
            
            if not ticket:
                await callback.answer("❌ Заявка не найдена", show_alert=True)
                return
            
            # Verify this is the ticket owner
            if ticket.user.external_id != callback.from_user.id:
                await callback.answer("❌ Это не ваша заявка", show_alert=True)
                return
            
            # Check if already rated
            if ticket.rating is not None:
                await callback.answer("Вы уже оценили эту заявку", show_alert=True)
                return
            
            # Save rating
            ticket.rating = rating
            await session.commit()
            
            # Update message to show rating received
            stars = "⭐" * rating
            await callback.message.edit_text(
                f"✅ <b>Ваш вопрос решен. Диалог закрыт.</b>\n\n"
                f"Спасибо за оценку: {stars}\n"
                f"<i>Ваш отзыв поможет нам улучшить качество поддержки!</i>",
                parse_mode="HTML"
            )
            
            await callback.answer("✅ Спасибо за оценку!")
            
            # Notify admin about the rating (optional)
            try:
                if rating <= 2:
                    # Low rating - notify admin
                    await bot.send_message(
                        settings.TG_ADMIN_ID,
                        f"⚠️ Низкая оценка ({stars}) для тикета #{ticket.daily_id} (ID: #{ticket.id})\n"
                        f"Студент: {callback.from_user.full_name or callback.from_user.username}\n"
                        f"Тема: {ticket.category.name if ticket.category else 'N/A'}",
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.warning(f"Failed to notify admin about low rating: {e}")
                
        except ValueError as e:
            logger.error(f"Invalid rating data: {callback.data}, error: {e}")
            await callback.answer("❌ Ошибка обработки оценки")
        except Exception as e:
            logger.error(f"Error processing rating: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при сохранении оценки")
