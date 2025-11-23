import re
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandObject
from sqlalchemy import select, func
from database.setup import new_session
from database.models import User, UserRole, FAQ, Ticket, TicketStatus, Message, SenderRole
from core.config import settings

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
            name = command.args.strip()
            session.add(Category(name=name))
            await session.commit()
            await message.answer(f"✅ Категория '{name}' добавлена.")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

# --- ОБРАБОТКА ОТВЕТОВ (Диалог) ---

# 1. Ответ СВАЙПОМ (Native Reply)
@router.message(F.reply_to_message)
async def admin_reply_native(message: types.Message, bot: Bot):
    async with new_session() as session:
        # Проверяем права
        if not await is_admin_or_mod(message.from_user.id, session): return

        # Ищем ID тикета (#123) в тексте, на который ответили
        origin_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        match = re.search(r"#(\d+)", origin_text)
        
        if not match:
            # Если админ отвечает просто так, не на уведомление — игнорируем или пишем подсказку
            return 

        ticket_id = int(match.group(1))
        answer_text = message.text
        
        await process_reply(bot, session, ticket_id, answer_text, message, close=False)

# 2. Команда /reply ID Текст
@router.message(Command("reply"))
async def admin_reply_command(message: types.Message, command: CommandObject, bot: Bot):
    async with new_session() as session:
        if not await is_admin_or_mod(message.from_user.id, session): return
        try:
            t_id, text = command.args.split(" ", 1)
            await process_reply(bot, session, int(t_id), text, message, close=False)
        except:
            await message.answer("Формат: /reply ID Текст")

# 3. Команда /close ID (Закрыть тикет принудительно)
@router.message(Command("close"))
async def admin_close_ticket(message: types.Message, command: CommandObject, bot: Bot):
    async with new_session() as session:
        if not await is_admin_or_mod(message.from_user.id, session): return
        try:
            t_id = int(command.args.strip())
            ticket = await session.get(Ticket, t_id)
            if ticket and ticket.status != TicketStatus.CLOSED:
                ticket.status = TicketStatus.CLOSED
                ticket.closed_at = func.now()
                await session.commit()
                await bot.send_message(ticket.user_id, "✅ <b>Ваш вопрос решен. Диалог закрыт.</b>", parse_mode="HTML")
                await message.answer(f"Тикет #{t_id} закрыт.")
            else:
                await message.answer("Тикет не найден или уже закрыт.")
        except:
            await message.answer("Формат: /close ID")

# --- ЛОГИКА ОТПРАВКИ ---
async def process_reply(bot, session, ticket_id, text, message, close=False):
    ticket = await session.get(Ticket, ticket_id)
    if ticket:
        # Отправляем студенту
        try:
            await bot.send_message(ticket.user_id, f"👨‍💼 <b>Ответ:</b>\n{text}", parse_mode="HTML")
            
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
