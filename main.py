import asyncio
import logging
from aiogram import Bot, Dispatcher
from core.config import settings
from core.logger import setup_logger
from database.setup import init_db
from handlers.telegram import router as tg_router  # <-- Берем роутер, а не функцию регистрации

async def main():
    # 1. Логирование
    setup_logger()
    logger = logging.getLogger(__name__)
    logger.info("Starting Support Bot...")

    # 2. База данных
    await init_db()
    logger.info("Database initialized.")

    # 3. Бот и Диспетчер
    bot = Bot(token=settings.TG_BOT_TOKEN)
    dp = Dispatcher()

    # 4. Подключаем логику (Роутер)
    dp.include_router(tg_router)

    # 5. Запуск
    logger.info("Telegram Bot starting polling...")
    await bot.delete_webhook(drop_pending_updates=True) # Удаляем вебхук на всякий случай
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
