from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy import select, delete
from database.setup import new_session
from database.models import User, UserRole, FAQ, Ticket, TicketStatus
from core.config import settings

router = Router()

async def is_admin_or_mod(user_id: int, session) -> tuple[bool, str]:
    """
    Checks if user is admin or moderator.
    Returns (is_allowed, role).
    """
    # Root admin always allowed
    if user_id == settings.TG_ADMIN_ID:
        return True, "admin"

    stmt = select(User).where(User.external_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user and user.role in [UserRole.ADMIN, UserRole.MODERATOR]:
        return True, user.role

    return False, "user"

async def is_admin(user_id: int, session) -> bool:
    if user_id == settings.TG_ADMIN_ID:
        return True

    stmt = select(User).where(User.external_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    return user and user.role == UserRole.ADMIN

# --- MODERATOR MANAGEMENT ---

@router.message(Command("add_mod"))
async def add_moderator(message: types.Message, command: CommandObject):
    async with new_session() as session:
        if not await is_admin(message.from_user.id, session):
            return # Silent ignore or generic message

        if not command.args:
            await message.answer("Usage: /add_mod {user_id}")
            return

        try:
            target_id = int(command.args.strip())
        except ValueError:
            await message.answer("Invalid ID.")
            return

        stmt = select(User).where(User.external_id == target_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("User not found in DB. They must start the bot first.")
            return

        user.role = UserRole.MODERATOR
        await session.commit()
        await message.answer(f"User {target_id} is now a MODERATOR.")

@router.message(Command("del_mod"))
async def del_moderator(message: types.Message, command: CommandObject):
    async with new_session() as session:
        if not await is_admin(message.from_user.id, session):
            return

        if not command.args:
            await message.answer("Usage: /del_mod {user_id}")
            return

        try:
            target_id = int(command.args.strip())
        except ValueError:
            await message.answer("Invalid ID.")
            return

        stmt = select(User).where(User.external_id == target_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("User not found.")
            return

        user.role = UserRole.USER
        await session.commit()
        await message.answer(f"User {target_id} is now a regular USER.")

# --- FAQ MANAGEMENT ---

@router.message(Command("add_faq"))
async def add_faq(message: types.Message, command: CommandObject):
    async with new_session() as session:
        allowed, _ = await is_admin_or_mod(message.from_user.id, session)
        if not allowed:
            return

        if not command.args:
            await message.answer("Usage: /add_faq {trigger} {answer}")
            return

        parts = command.args.split(" ", 1)
        if len(parts) < 2:
            await message.answer("Usage: /add_faq {trigger} {answer}")
            return

        trigger, answer = parts
        trigger = trigger.lower()

        # Check existing
        stmt = select(FAQ).where(FAQ.trigger_word == trigger)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.answer_text = answer
            await message.answer(f"Updated FAQ for '{trigger}'.")
        else:
            session.add(FAQ(trigger_word=trigger, answer_text=answer))
            await message.answer(f"Added FAQ for '{trigger}'.")

        await session.commit()

@router.message(Command("del_faq"))
async def del_faq(message: types.Message, command: CommandObject):
    async with new_session() as session:
        allowed, _ = await is_admin_or_mod(message.from_user.id, session)
        if not allowed:
            return

        if not command.args:
            await message.answer("Usage: /del_faq {trigger}")
            return

        trigger = command.args.strip().lower()
        stmt = select(FAQ).where(FAQ.trigger_word == trigger)
        result = await session.execute(stmt)
        faq_item = result.scalar_one_or_none()

        if faq_item:
            await session.delete(faq_item)
            await session.commit()
            await message.answer(f"Deleted FAQ '{trigger}'.")
        else:
            await message.answer(f"FAQ '{trigger}' not found.")

@router.message(Command("list_faq"))
async def list_faq(message: types.Message):
    async with new_session() as session:
        allowed, _ = await is_admin_or_mod(message.from_user.id, session)
        if not allowed:
            return

        stmt = select(FAQ).order_by(FAQ.trigger_word)
        result = await session.execute(stmt)
        faqs = result.scalars().all()

        if not faqs:
            await message.answer("No FAQs found.")
            return

        text = "\n".join([f"- `{f.trigger_word}`: {f.answer_text[:50]}..." for f in faqs])
        await message.answer(f"📜 <b>FAQ List:</b>\n{text}", parse_mode="HTML")

# --- TICKET REPLY ---

@router.message(Command("reply"))
async def admin_reply(message: types.Message, command: CommandObject, bot):
    async with new_session() as session:
        allowed, _ = await is_admin_or_mod(message.from_user.id, session)
        if not allowed:
            return

        if not command.args:
             await message.answer("Usage: /reply {ticket_id} {text}")
             return

        try:
            t_id_str, text = command.args.split(" ", 1)
            t_id = int(t_id_str)
        except ValueError:
            await message.answer("Usage: /reply {ticket_id} {text}")
            return

        ticket = await session.get(Ticket, t_id)
        if ticket:
            try:
                await bot.send_message(ticket.user_id, f"👨‍💼 <b>Ответ:</b>\n{text}", parse_mode="HTML")
                ticket.status = TicketStatus.CLOSED
                await session.commit()
                await message.answer(f"Тикет #{t_id} закрыт.")
            except Exception as e:
                await message.answer(f"Ошибка отправки: {e}")
        else:
            await message.answer("Тикет не найден.")
