import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Ticket, User, Message, TicketStatus, SourceType, SenderRole
from core.config import settings
from aiogram import Bot

logger = logging.getLogger(__name__)

async def create_ticket(session: AsyncSession, user_id: int, source: str, text: str, bot: Bot, category: str = "General"):
    # 1. Находим или создаем пользователя
    # Используем select().limit(1) для эффективности
    result = await session.execute(select(User).where(User.external_id == user_id, User.source == source).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        # Если юзера нет, создаем. Имя обновим потом через апдейт, если нужно.
        user = User(external_id=user_id, source=source, username="User")
        session.add(user)
        await session.flush() # Чтобы получить user.id сразу
    
    # 2. Ищем активный тикет
    result = await session.execute(
        select(Ticket).where(
            Ticket.user_id == user.id, 
            Ticket.status.in_([TicketStatus.NEW, TicketStatus.IN_PROGRESS])
        ).limit(1)
    )
    active_ticket = result.scalar_one_or_none()

    is_new = False

    # 3. Если нет активного — создаем новый
    if not active_ticket:
        is_new = True
        # В начало текста добавляем категорию для наглядности
        question_text = f"[{category}] {text}"
        active_ticket = Ticket(
            user_id=user.id, 
            source=source, 
            question_text=question_text, 
            status=TicketStatus.NEW
        )
        session.add(active_ticket)
        await session.flush() # Получаем ID тикета
    
    # 4. Сохраняем сообщение в историю
    msg = Message(ticket_id=active_ticket.id, sender_role=SenderRole.USER, text=text)
    session.add(msg)
    
    # Важно: комитим изменения в БД ДО отправки уведомлений
    # Если отправка упадет, данные уже будут сохранены
    await session.commit()

    # 5. Уведомление админа (Безопасный блок)
    if is_new:
        try:
            admin_text = (
                f"🔥 <b>Новый тикет #{active_ticket.id}</b>\n"
                f"Категория: {category}\n"
                f"Текст: {text}\n\n"
                f"Ответить: <code>/reply {active_ticket.id} ответ</code>"
            )
            await bot.send_message(settings.TG_ADMIN_ID, admin_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"⚠️ Не удалось отправить уведомление админу: {e}")

    return active_ticket
