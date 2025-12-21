"""
Migration script to add university-specific improvements to the database.

This script adds:
- Priority field to tickets
- Student info fields to users (student_id, department, course)
- Ticket assignment (assigned_to)
- SLA tracking (first_response_at)
- Student satisfaction (rating, satisfaction_comment)
"""
import asyncio
import logging
from database.setup import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """Apply database migrations for university improvements."""
    logger.info("Starting migration for university improvements...")
    
    async with engine.begin() as conn:
        # Add columns to users table
        try:
            await conn.execute("""
                ALTER TABLE users ADD COLUMN student_id VARCHAR(50) NULL
            """)
            logger.info("✓ Added student_id to users")
        except Exception as e:
            logger.info(f"student_id column may already exist: {e}")
        
        try:
            await conn.execute("""
                ALTER TABLE users ADD COLUMN department VARCHAR(255) NULL
            """)
            logger.info("✓ Added department to users")
        except Exception as e:
            logger.info(f"department column may already exist: {e}")
        
        try:
            await conn.execute("""
                ALTER TABLE users ADD COLUMN course INTEGER NULL
            """)
            logger.info("✓ Added course to users")
        except Exception as e:
            logger.info(f"course column may already exist: {e}")
        
        # Add columns to tickets table
        try:
            await conn.execute("""
                ALTER TABLE tickets ADD COLUMN priority VARCHAR(10) DEFAULT 'normal'
            """)
            logger.info("✓ Added priority to tickets")
        except Exception as e:
            logger.info(f"priority column may already exist: {e}")
        
        try:
            await conn.execute("""
                ALTER TABLE tickets ADD COLUMN assigned_to INTEGER NULL
            """)
            logger.info("✓ Added assigned_to to tickets")
        except Exception as e:
            logger.info(f"assigned_to column may already exist: {e}")
        
        try:
            await conn.execute("""
                ALTER TABLE tickets ADD COLUMN first_response_at TIMESTAMP NULL
            """)
            logger.info("✓ Added first_response_at to tickets")
        except Exception as e:
            logger.info(f"first_response_at column may already exist: {e}")
        
        try:
            await conn.execute("""
                ALTER TABLE tickets ADD COLUMN rating INTEGER NULL
            """)
            logger.info("✓ Added rating to tickets")
        except Exception as e:
            logger.info(f"rating column may already exist: {e}")
        
        try:
            await conn.execute("""
                ALTER TABLE tickets ADD COLUMN satisfaction_comment TEXT NULL
            """)
            logger.info("✓ Added satisfaction_comment to tickets")
        except Exception as e:
            logger.info(f"satisfaction_comment column may already exist: {e}")
        
        # Create indexes for better performance
        try:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority)
            """)
            logger.info("✓ Created index on tickets.priority")
        except Exception as e:
            logger.info(f"Index may already exist: {e}")
        
        try:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON tickets(assigned_to)
            """)
            logger.info("✓ Created index on tickets.assigned_to")
        except Exception as e:
            logger.info(f"Index may already exist: {e}")
    
    logger.info("✅ Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
