import asyncio
import logging
from aiogram import Bot as AiogramBot, Dispatcher

from core.config import settings
from core.logger import setup_logger
from database.setup import init_db
from handlers.telegram import register_handlers as register_tg_handlers

logger = setup_logger("main")

async def main():
    logger.info("Starting Support Bot...")

    # Initialize Database
    await init_db()
    logger.info("Database initialized.")

    # Initialize Bots
    tg_bot = AiogramBot(token=settings.TG_BOT_TOKEN)
    dp = Dispatcher()

    # Register Handlers
    register_tg_handlers(dp)

    # Run Bots
    logger.info("Telegram Bot starting polling...")

    try:
        await dp.start_polling(tg_bot)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await tg_bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
