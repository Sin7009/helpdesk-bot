import random
from vkbottle.bot import Bot, Message
from core.config import settings
from core.logger import setup_logger
from database.setup import get_session
from database.models import SourceType, SenderRole
from services.user_service import get_or_create_user
from services.ticket_service import (
    get_open_ticket,
    create_ticket,
    add_message_to_ticket
)
from aiogram import Bot as AiogramBot

logger = setup_logger("vk_bot")

# We need the TG bot to notify admin
tg_bot: AiogramBot | None = None

def set_tg_bot(bot: AiogramBot):
    """
    Sets the global Telegram Bot instance for notifying the admin about VK events.
    """
    global tg_bot
    tg_bot = bot

async def message_handler(message: Message):
    """
    Handles incoming private messages from VK users.

    It performs the following steps:
    1. Retrieves or creates the User in the database based on VK ID.
    2. Checks for an existing open ticket for this user.
    3. If an open ticket exists, appends the message to it and notifies the admin via Telegram.
    4. If no open ticket exists, creates a new ticket with the message and notifies the admin via Telegram.

    Args:
        message (Message): The incoming VK message object.
    """
    async for session in get_session():
        user = await get_or_create_user(
            session,
            external_id=message.from_id,
            source=SourceType.VK,
            # VK bottle doesn't always give username/fullname in message event easily without extra call
            # We'll assume we can get it or just leave it None/Generic for now to save API calls,
            # or fetch it if needed. For MVP, let's try to fetch if possible, or just skip.
            username=None,
            full_name=None
        )

        # Try to get user info if we want (optional but nice)
        # users_info = await message.ctx_api.users.get(message.from_id)
        # if users_info:
        #     user.full_name = f"{users_info[0].first_name} {users_info[0].last_name}"
        #     session.add(user)
        #     await session.commit()

        ticket = await get_open_ticket(session, user.id)

        if ticket:
            await add_message_to_ticket(session, ticket.id, message.text, SenderRole.USER)
            await message.answer("Message added to your open ticket.")

            if tg_bot:
                await tg_bot.send_message(
                    settings.TG_ADMIN_ID,
                    f"New message in Ticket #{ticket.id} from VK User {user.id} (ID: {message.from_id}):\n{message.text}"
                )
        else:
            ticket = await create_ticket(session, user.id, SourceType.VK, message.text)
            await message.answer(f"Ticket #{ticket.id} created. Support will reply soon.")

            if tg_bot:
                await tg_bot.send_message(
                    settings.TG_ADMIN_ID,
                    f"New Ticket #{ticket.id} created by VK User {user.id} (ID: {message.from_id}):\n{message.text}"
                )

def register_handlers(bot: Bot):
    """
    Registers the VK message handler for private messages.
    """
    bot.on.private_message(text="<msg>")(message_handler)
