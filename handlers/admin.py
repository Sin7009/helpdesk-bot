import re
import html
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandObject
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from database.setup import new_session
from database.models import User, UserRole, FAQ, Ticket, TicketStatus, Message, SenderRole, Category
from core.config import settings
from core.constants import TICKET_ID_PATTERN

router = Router()

# --- ПРОВЕРКА ПРАВ ---
async def is_admin_or_mod(user_id: int, session) -> bool:
    if user_id == settings.TG_ADMIN_ID:
        return True
    stmt = select(User).where(User.external_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    return user and user.role in [UserRole.ADMIN, UserRole.MODERATOR]

async def is_root_admin(user_id: int) -> bool:
    return user_id == settings.TG_ADMIN_ID

# --- УПРАВЛЕНИЕ (Модераторы / FAQ / Категории) ---
# (Оставляем всё как было, сокращено для ясности)

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

# --- ОБРАБОТКА ОТВЕТОВ (Диалог) ---

# 1. Ответ СВАЙПОМ (Native Reply)
@router.message(F.reply_to_message)
async def admin_reply_native(message: types.Message, bot: Bot, session: AsyncSession):
    # 1. Проверка прав
    if not await is_admin_or_mod(message.from_user.id, session): return

    # 2. Проверка: отвечаем ли мы боту?
    bot_obj = await bot.get_me()
    if message.reply_to_message.from_user.id != bot_obj.id:
        return

    # 3. Парсинг ID
    origin_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    
    # Ищем ID: #123 (Основной формат)
    match = re.search(r"ID:\s*#(\d+)", origin_text)
    
    # Fallback (Если вдруг старый формат #123)
    if not match:
        match = re.search(r"#(\d+)", origin_text)

    if not match:
        # Если не нашли ID тикета — просто игнорируем
        return

    ticket_id = int(match.group(1))
    answer_text = message.text

    await process_reply(bot, session, ticket_id, answer_text, message, close=False)

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

        if ticket and ticket.status != TicketStatus.CLOSED:
            ticket.status = TicketStatus.CLOSED
            ticket.closed_at = func.now()
            await session.commit()

            # Try notify user
            try:
                await bot.send_message(ticket.user.external_id, "✅ <b>Ваш вопрос решен. Диалог закрыт.</b>", parse_mode="HTML")
            except: pass

            await message.answer(f"Тикет #{t_id} закрыт.")
        else:
            await message.answer("Тикет не найден или уже закрыт.")
    except ValueError:
        await message.answer("Формат: /close ID")
            
@router.callback_query(F.data.startswith("close_"))
async def close_ticket_btn(callback: types.CallbackQuery, bot: Bot):
    async with new_session() as session:
        if not await is_admin_or_mod(callback.from_user.id, session):
            await callback.answer("У вас нет прав.", show_alert=True)
            return

        t_id = int(callback.data.split("_")[1])
        # Use selectinload to fetch user eagerly for notification
        stmt = select(Ticket).options(selectinload(Ticket.user)).where(Ticket.id == t_id)
        result = await session.execute(stmt)
        ticket = result.scalar_one_or_none()
        
        if ticket and ticket.status != TicketStatus.CLOSED:
            ticket.status = TicketStatus.CLOSED
            ticket.closed_at = func.now()
            await session.commit()
            
            # Уведомляем студента
            try:
                await bot.send_message(ticket.user.external_id, "✅ <b>Ваш вопрос решен. Диалог закрыт.</b>", parse_mode="HTML")
            except: pass
            
            # Экранируем текст сообщения перед редактированием, так как используем parse_mode="HTML"
            # и callback.message.text возвращает простой текст, который может содержать спецсимволы (<, >)
            original_text = callback.message.text

            if original_text:
                safe_text = html.escape(original_text)
                await callback.message.edit_text(f"{safe_text}\n\n✅ <b>ЗАКРЫТО</b>", parse_mode="HTML")
            elif callback.message.caption:
                # Если это медиа с подписью, мы не можем превратить его в текст через edit_text
                # Лучше просто удалить кнопки (edit_reply_markup) и отправить новое сообщение, или оставить как есть
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.reply("✅ <b>Тикет закрыт.</b>", parse_mode="HTML")
            else:
                # Если ничего нет (странно), просто пишем ответ
                await callback.message.answer("✅ <b>Тикет закрыт.</b>", parse_mode="HTML")
                # И убираем кнопки
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except:
                    pass
        else:
            await callback.answer("Тикет уже закрыт или не найден.")

# --- ЛОГИКА ОТПРАВКИ ---
async def process_reply(bot, session, ticket_id, text, message, close=False):
    # Используем stmt вместо get, чтобы подгрузить User сразу
    stmt = select(Ticket).options(selectinload(Ticket.user)).where(Ticket.id == ticket_id)
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket:
        user = ticket.user # Теперь это безопасно, данные уже в памяти
        # Отправляем студенту
        try:
            # 🎨 Palette UX: Добавляем подсказку, как ответить
            reply_hint = "\n\n<i>(Чтобы ответить, просто отправьте сообщение)</i>" if not close else ""

            await bot.send_message(
                user.external_id,
                f"👨‍💼 <b>Ответ:</b>\n{text}{reply_hint}",
                parse_mode="HTML"
            )
            
            # Сохраняем ответ Админа в историю переписки
            msg = Message(ticket_id=ticket.id, sender_role=SenderRole.ADMIN, text=text)
            session.add(msg)
            
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
            await message.react([types.ReactionTypeEmoji(emoji="👍")]) # Ставим лайк сообщению админа вместо спама текстом
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки: {e}")
    else:
        await message.answer("❌ Тикет не найден.")
