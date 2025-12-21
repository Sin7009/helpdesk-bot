# Database Migrations with Alembic

This project now uses [Alembic](https://alembic.sqlalchemy.org/) for database schema migrations, providing a robust and versioned approach to database changes.

## Why Alembic?

The previous `migrate_db.py` script used manual try-except logic to detect and apply schema changes. This approach had several issues:

1. **No version tracking** - No way to know which migrations have been applied
2. **Error-prone** - Easy to lose data or desynchronize schemas across environments
3. **Manual maintenance** - Every schema change required custom SQL in the script
4. **No rollback** - Couldn't revert changes if something went wrong

Alembic solves all these problems with:
- ✅ Automatic schema version tracking
- ✅ Generated migration files from model changes
- ✅ Upgrade and downgrade support
- ✅ Complete migration history

## Installation

Alembic is included in the project dependencies:

```bash
pip install alembic  # Already included in requirements
```

## Initial Setup (For New Installations)

If you're setting up a fresh database:

```bash
# Run all migrations to create the database schema
alembic upgrade head
```

This will create all tables including the new `DailyTicketCounter` table for atomic ticket ID generation.

## Upgrading Existing Database

If you have an existing database from before Alembic was added:

### Option 1: Mark Current State (Recommended for Production)

If your database already has all the tables from the initial migration:

```bash
# Mark the database as being at the initial migration without running it
alembic stamp head
```

This tells Alembic "the database is already at the latest version, don't create tables that exist."

### Option 2: Clean Migration (For Development)

If you want to start fresh:

```bash
# Backup your data first!
cp support.db support.db.backup

# Drop and recreate with Alembic
rm support.db
alembic upgrade head
```

## Creating New Migrations

When you modify the database models in `database/models.py`:

```bash
# Auto-generate a migration from model changes
alembic revision --autogenerate -m "Add new field to User model"

# Review the generated file in alembic/versions/
# Edit if needed, then apply it
alembic upgrade head
```

## Common Commands

```bash
# See current database version
alembic current

# View migration history
alembic history

# Upgrade to latest
alembic upgrade head

# Upgrade by one version
alembic upgrade +1

# Downgrade by one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>

# View SQL that would be executed (dry run)
alembic upgrade head --sql
```

## Migration for DailyTicketCounter

The initial migration (revision `59e1544c328e`) includes the new `daily_ticket_counter` table which fixes the race condition in ticket ID generation.

**For existing databases:** After running `alembic stamp head` or `alembic upgrade head`, you may need to initialize counters for today:

```python
# Run this once if you have existing tickets created today
python -c "
from database.setup import new_session
from database.models import DailyTicketCounter
from services.ticket_service import get_next_daily_id
import asyncio
import datetime

async def init_counter():
    async with new_session() as session:
        # This will initialize today's counter
        daily_id = await get_next_daily_id(session)
        await session.commit()
        print(f'Initialized daily counter to {daily_id}')

asyncio.run(init_counter())
"
```

## Docker Considerations

When using Docker, run migrations during container startup:

```dockerfile
# In your Dockerfile or docker-compose command
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
```

Or create a startup script:

```bash
#!/bin/bash
# startup.sh
alembic upgrade head
python main.py
```

## Configuration

The Alembic configuration is in:
- `alembic.ini` - Main configuration file
- `alembic/env.py` - Environment setup (uses async SQLAlchemy)
- `alembic/versions/` - Migration files

The database URL is automatically configured from `core/config.py` settings.

## Troubleshooting

### "No such table: alembic_version"

This means Alembic hasn't been initialized. Run:

```bash
alembic upgrade head
```

### "Target database is not up to date"

Your code expects a newer schema than the database has. Run:

```bash
alembic upgrade head
```

### "Table already exists" error

The database has tables but Alembic doesn't know about them. Use:

```bash
alembic stamp head
```

### Migration conflicts

If multiple developers create migrations at the same time:

```bash
# Merge the branch points
alembic merge heads -m "Merge migrations"
```

## Best Practices

1. **Always review auto-generated migrations** - Alembic is smart but not perfect
2. **Test migrations on a copy** before applying to production
3. **Backup before migration** - `cp support.db support.db.backup`
4. **Commit migration files** to git with your model changes
5. **Don't edit applied migrations** - Create a new migration instead
6. **Document complex migrations** with comments in the migration file

## Replacing migrate_db.py

The old `migrate_db.py` script is now deprecated. Use Alembic instead:

| Old Way | New Way |
|---------|---------|
| `python migrate_db.py` | `alembic upgrade head` |
| Manual ALTER TABLE | `alembic revision --autogenerate` |
| No rollback | `alembic downgrade -1` |
| No version tracking | `alembic current` |

## Learn More

- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [SQLAlchemy 2.0 with Alembic](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)
