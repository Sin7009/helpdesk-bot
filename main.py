import asyncio
import logging
from aiogram import Bot as AiogramBot, Dispatcher
from vkbottle.bot import Bot as VkBot

from core.config import settings
from core.logger import setup_logger
from database.setup import init_db
from handlers.telegram import register_handlers as register_tg_handlers, set_vk_api
from handlers.vk import register_handlers as register_vk_handlers, set_tg_bot

logger = setup_logger("main")

async def main():
    logger.info("Starting Support Bot...")

    # Initialize Database
    await init_db()
    logger.info("Database initialized.")

    # Initialize Bots
    tg_bot = AiogramBot(token=settings.TG_BOT_TOKEN)
    dp = Dispatcher()

    vk_bot = VkBot(token=settings.VK_TOKEN)

    # Wire up dependencies
    set_vk_api(vk_bot.api)
    set_tg_bot(tg_bot)

    # Register Handlers
    register_tg_handlers(dp)
    register_vk_handlers(vk_bot)

    # Run Bots
    logger.info("Bots starting polling...")

    try:
        await asyncio.gather(
            dp.start_polling(tg_bot),
            vk_bot.run_polling(),
        )
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await tg_bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
