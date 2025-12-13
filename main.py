import asyncio
import logging
from aiogram import Bot, Dispatcher
from core.config import settings
from core.logger import setup_logger
from database.setup import init_db, new_session
from handlers.telegram import router as tg_router
from handlers.admin import router as admin_router
from services.scheduler import setup_scheduler
from services.user_service import ensure_admin_exists

async def main():
    # 1. Логирование
    setup_logger("bot")
    logger = logging.getLogger(__name__)
    logger.info("Starting Support Bot v2.0...")

    # 2. База данных
    await init_db()
    logger.info("Database initialized.")

    # 2.1. Ensure Admin exists
    async with new_session() as session:
        await ensure_admin_exists(session)
    logger.info("Admin checks completed.")

    # 3. Бот и Диспетчер
    bot = Bot(token=settings.TG_BOT_TOKEN)
    dp = Dispatcher()

    # 4. Подключаем логику (Роутер)
    dp.include_router(admin_router) # Admin router first to catch commands
    dp.include_router(tg_router)

    # 5. Запуск планировщика
    scheduler = setup_scheduler(bot)
    logger.info("Scheduler started.")

    # 6. Запуск
    logger.info("Telegram Bot starting polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
