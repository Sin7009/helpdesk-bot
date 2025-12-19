import asyncio
import logging
from database.setup import engine, Base
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    logger.info("Starting migration...")
    async with engine.begin() as conn:
        # Create new tables (Categories)
        await conn.run_sync(Base.metadata.create_all)

        # Check and alter Tickets table
        # SQLite ADD COLUMN support is limited but works for basic types
        try:
            await conn.execute(text("ALTER TABLE tickets ADD COLUMN daily_id INTEGER DEFAULT 0"))
            logger.info("Added daily_id to tickets")
        except Exception as e:
            logger.warning(f"daily_id column might already exist: {e}")

        try:
            await conn.execute(text("ALTER TABLE tickets ADD COLUMN category_id INTEGER REFERENCES categories(id)"))
            logger.info("Added category_id to tickets")
        except Exception as e:
            logger.warning(f"category_id column might already exist: {e}")

        try:
            await conn.execute(text("ALTER TABLE tickets ADD COLUMN summary TEXT"))
            logger.info("Added summary to tickets")
        except Exception as e:
            logger.warning(f"summary column might already exist: {e}")

        try:
            await conn.execute(text("ALTER TABLE tickets ADD COLUMN closed_at TIMESTAMP"))
            logger.info("Added closed_at to tickets")
        except Exception as e:
            logger.warning(f"closed_at column might already exist: {e}")

        try:
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_messages_ticket_id ON messages (ticket_id)"))
            logger.info("Added index on messages.ticket_id")
        except Exception as e:
            logger.warning(f"Could not create index on messages.ticket_id: {e}")

        # Seed categories if empty
        try:
            # We can't easily check for existence in raw SQL in a cross-DB way easily,
            # but we can try to insert and ignore duplicate errors if unique constraint exists
            # Or just use python logic.
            pass
        except Exception as e:
            pass

    logger.info("Migration complete.")

async def seed_categories():
    from database.setup import new_session
    from database.models import Category
    from sqlalchemy import select

    default_cats = ["Учеба", "IT", "Справки", "Общежитие", "Другое"]

    async with new_session() as session:
        for cat_name in default_cats:
            result = await session.execute(select(Category).where(Category.name == cat_name))
            if not result.scalar_one_or_none():
                session.add(Category(name=cat_name))
        await session.commit()
    logger.info("Default categories seeded.")

if __name__ == "__main__":
    asyncio.run(migrate())
    asyncio.run(seed_categories())
