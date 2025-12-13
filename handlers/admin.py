import re
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database.models import User, UserRole, FAQ, Ticket, TicketStatus, Message, SenderRole, Category
from services.faq_service import FAQService
from core.config import settings
from core.constants import TICKET_ID_PATTERN

router = Router()

# --- ПРОВЕРКА ПРАВ ---
async def is_admin_or_mod(user_id: int, session: AsyncSession) -> bool:
    if user_id == settings.TG_ADMIN_ID:
        return True
    stmt = select(User).where(User.external_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    return user and user.role in [UserRole.ADMIN, UserRole.MODERATOR]

# --- УПРАВЛЕНИЕ (Модераторы / FAQ / Категории) ---

@router.message(Command("add_category"))
async def add_category_cmd(message: types.Message, command: CommandObject, session: AsyncSession):
    if not await is_admin_or_mod(message.from_user.id, session): return
    try:
        name = command.args.strip()
        session.add(Category(name=name))
        await session.commit()
        await message.answer(f"✅ Категория '{name}' добавлена.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("add_faq"))
async def add_faq_cmd(message: types.Message, command: CommandObject, session: AsyncSession):
    if not await is_admin_or_mod(message.from_user.id, session): return
    try:
        # Format: /add_faq trigger | answer
        args = command.args.split("|", 1)
        if len(args) != 2: raise ValueError
        trigger, answer = args[0].strip(), args[1].strip()

        session.add(FAQ(trigger_word=trigger, answer_text=answer))
        await session.commit()
        await FAQService.refresh(session) # Refresh Cache
        await message.answer(f"✅ FAQ '{trigger}' добавлен.")
    except Exception:
        await message.answer("Формат: /add_faq Триггер | Ответ")

@router.message(Command("del_faq"))
async def del_faq_cmd(message: types.Message, command: CommandObject, session: AsyncSession):
    if not await is_admin_or_mod(message.from_user.id, session): return
    try:
        trigger = command.args.strip()
        stmt = select(FAQ).where(FAQ.trigger_word == trigger)
        result = await session.execute(stmt)
        faq = result.scalar_one_or_none()
        if faq:
            await session.delete(faq)
            await session.commit()
            await FAQService.refresh(session) # Refresh Cache
            await message.answer(f"✅ FAQ '{trigger}' удален.")
        else:
            await message.answer("FAQ не найден.")
    except Exception:
         await message.answer("Формат: /del_faq Триггер")

@router.message(Command("list_faq"))
async def list_faq_cmd(message: types.Message, session: AsyncSession):
    if not await is_admin_or_mod(message.from_user.id, session): return
    faqs = FAQService.get_cache()
    if not faqs:
        await message.answer("База пуста.")
        return
    text = "\n".join([f"- {f.trigger_word}" for f in faqs])
    await message.answer(f"Список FAQ:\n{text}")


# --- ОБРАБОТКА ОТВЕТОВ (Диалог) ---

# 1. Ответ СВАЙПОМ (Native Reply)
@router.message(F.reply_to_message)
async def admin_reply_native(message: types.Message, bot: Bot, session: AsyncSession):
    # Проверяем права
    if not await is_admin_or_mod(message.from_user.id, session): return

    # Проверка, что отвечаем боту
    bot_obj = await bot.get_me()
    if message.reply_to_message.from_user.id != bot_obj.id:
        return

    # Ищем ID тикета (#123) в тексте, на который ответили
    # The notification text now contains "(ID: #123)"
    origin_text = message.reply_to_message.text or message.reply_to_message.caption or ""

    # Updated regex to match the new format OR the old format just in case
    match = re.search(TICKET_ID_PATTERN, origin_text)

    # Fallback to just #(\d+) if specific format not found (though risky if other # exist, but okay for now)
    if not match:
         match = re.search(r"#(\d+)", origin_text)

    if not match:
        # Если админ отвечает просто так, не на уведомление — игнорируем или пишем подсказку
        return

    ticket_id = int(match.group(1))
    answer_text = message.text

    await process_reply(bot, session, ticket_id, answer_text, message, close=False)

# 2. Команда /reply ID Текст
@router.message(Command("reply"))
async def admin_reply_command(message: types.Message, command: CommandObject, bot: Bot, session: AsyncSession):
    if not await is_admin_or_mod(message.from_user.id, session): return
    try:
        t_id, text = command.args.split(" ", 1)
        await process_reply(bot, session, int(t_id), text, message, close=False)
    except:
        await message.answer("Формат: /reply ID Текст")

# 3. Команда /close ID (Закрыть тикет принудительно)
@router.message(Command("close"))
async def admin_close_ticket(message: types.Message, command: CommandObject, bot: Bot, session: AsyncSession):
    if not await is_admin_or_mod(message.from_user.id, session): return
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
    except:
        await message.answer("Формат: /close ID")
            
@router.callback_query(F.data.startswith("close_"))
async def close_ticket_btn(callback: types.CallbackQuery, bot: Bot, session: AsyncSession):
    if not await is_admin_or_mod(callback.from_user.id, session):
        await callback.answer("У вас нет прав.", show_alert=True)
        return

    try:
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
            
            await callback.message.edit_text(f"{callback.message.text}\n\n✅ <b>ЗАКРЫТО</b>", parse_mode="HTML")
        else:
            await callback.answer("Тикет уже закрыт или не найден.")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)

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
            await bot.send_message(user.external_id, f"👨‍💼 <b>Ответ:</b>\n{text}", parse_mode="HTML")
            
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
