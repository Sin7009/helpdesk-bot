import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import setup_logger
from database.setup import get_session
from database.models import SourceType, SenderRole
from services.user_service import get_or_create_user
from services.ticket_service import (
    get_open_ticket,
    create_ticket,
    add_message_to_ticket,
    get_ticket_by_id,
    close_ticket
)

logger = setup_logger("tg_bot")

async def handle_start(message: Message):
    """
    Handles the /start command.
    """
    await message.answer("Welcome to Support Bot! Send your question here.")

async def handle_user_message(message: Message, bot: Bot):
    """
    Handles incoming text messages from Telegram users.

    If the message is from the admin, it is currently ignored unless it's a command.
    For regular users, it checks for an existing open ticket.
    - If an open ticket exists, the message is appended to it and the admin is notified.
    - If no open ticket exists, a new one is created with the message content, and the admin is notified.

    Args:
        message (Message): The incoming Telegram message.
        bot (Bot): The Telegram bot instance.
    """
    if message.from_user.id == settings.TG_ADMIN_ID:
        # Admin sent a message without command? Ignore or handle differently.
        # For now, assume admin only uses commands or replies.
        # If admin replies to a forwarded message, we might want to handle it,
        # but the requirement says `/reply {ticket_id} {text}`.
        return

    async for session in get_session():
        user = await get_or_create_user(
            session,
            external_id=message.from_user.id,
            source=SourceType.TELEGRAM,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )

        ticket = await get_open_ticket(session, user.id)

        if ticket:
            await add_message_to_ticket(session, ticket.id, message.text, SenderRole.USER)
            await message.answer("Message added to your open ticket.")
            # Notify admin about new message in existing ticket?
            # Requirement: "Append the incoming message to the existing ticket"
            # It doesn't explicitly say notify admin again, but usually support systems do.
            # I'll notify admin for context.
            await bot.send_message(
                settings.TG_ADMIN_ID,
                f"New message in Ticket #{ticket.id} from User {user.id} ({user.full_name}):\n{message.text}"
            )
        else:
            ticket = await create_ticket(session, user.id, SourceType.TELEGRAM, message.text)
            await message.answer(f"Ticket #{ticket.id} created. Support will reply soon.")
            await bot.send_message(
                settings.TG_ADMIN_ID,
                f"New Ticket #{ticket.id} created by User {user.id} ({user.full_name}):\n{message.text}"
            )

async def handle_admin_reply(message: Message, bot: Bot):
    """
    Handles the admin's reply command `/reply {ticket_id} {text}`.

    This function:
    1. Parses the command to extract the ticket ID and reply text.
    2. Retrieves the ticket from the database.
    3. Saves the admin's reply as a message in the ticket history.
    4. Routes the reply to the correct platform (Telegram or VK) based on the ticket's source.

    Args:
        message (Message): The incoming command message from the admin.
        bot (Bot): The Telegram bot instance.
    """
    if message.from_user.id != settings.TG_ADMIN_ID:
        return

    # Format: /reply {ticket_id} {text}
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /reply {ticket_id} {text}")
        return

    try:
        ticket_id = int(parts[1])
        reply_text = parts[2]
    except ValueError:
        await message.answer("Invalid ticket ID.")
        return

    async for session in get_session():
        ticket = await get_ticket_by_id(session, ticket_id)
        if not ticket:
            await message.answer("Ticket not found.")
            return

        await add_message_to_ticket(session, ticket.id, reply_text, SenderRole.ADMIN)

        # Route response
        if ticket.source == SourceType.TELEGRAM:
            try:
                await bot.send_message(ticket.user.external_id, f"Support Reply:\n{reply_text}")
                await message.answer(f"Reply sent to TG user {ticket.user.external_id}.")

                # Close the ticket as per requirement
                await close_ticket(session, ticket.id)
                await message.answer(f"Ticket #{ticket.id} closed.")
            except Exception as e:
                logger.error(f"Failed to send to TG user: {e}")
                await message.answer(f"Failed to send to TG user: {e}")
        else:
            await message.answer(f"Unsupported source type: {ticket.source}")

def register_handlers(dp: Dispatcher):
    """
    Registers Telegram message handlers with the dispatcher.
    """
    dp.message.register(handle_start, Command("start"))
    dp.message.register(handle_admin_reply, Command("reply"))
    dp.message.register(handle_user_message, F.text)
