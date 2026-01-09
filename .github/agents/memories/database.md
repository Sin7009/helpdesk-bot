# Agent Memories: Database

This file contains agent memories related to database.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---

## SQLAlchemy 2.0

**Category:** database  
**Tags:** `sqlalchemy`, `database`, `orm`  
**Created:** 2026-01-09 15:24:16

### Fact
Используй новый синтаксис SQLAlchemy 2.0 с Mapped[] и mapped_column()

### Why This Matters
SQLAlchemy 2.0 предоставляет улучшенную типизацию и производительность. Старый стиль deprecated.

### Source
database/models.py:35-100

---

## Daily ID счётчик

**Category:** database  
**Tags:** `tickets`, `concurrency`, `database`  
**Created:** 2026-01-09 15:24:16

### Fact
daily_id для тикетов генерируется атомарно через DailyTicketCounter таблицу

### Why This Matters
Атомарный счётчик предотвращает race conditions при конкурентном создании тикетов.

### Source
database/repositories/ticket_repository.py, database/models.py:127-135

---

## Alembic Миграции

**Category:** database  
**Tags:** `database`, `migrations`, `alembic`  
**Created:** 2026-01-09 15:24:16

### Fact
Используй Alembic для всех изменений схемы БД. Не изменяй models.py без создания миграции.

### Why This Matters
Alembic обеспечивает контролируемые и обратимые изменения схемы БД, критично для продакшена.

### Source
alembic/, ALEMBIC_GUIDE.md

---
