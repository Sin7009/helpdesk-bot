# Agent Memories: Architecture

This file contains agent memories related to architecture.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---

## Middleware сессии

**Category:** architecture  
**Tags:** `middleware`, `database`, `aiogram`  
**Created:** 2026-01-09 15:24:16

### Fact
Используй DbSessionMiddleware для автоматической инъекции AsyncSession в handlers

### Why This Matters
Централизованное управление сессиями БД предотвращает утечки соединений и упрощает код handlers.

### Source
middlewares/db.py, handlers/telegram.py

---

## Pydantic Settings

**Category:** architecture  
**Tags:** `configuration`, `pydantic`, `env`  
**Created:** 2026-01-09 15:24:16

### Fact
Все конфигурации через Pydantic Settings с валидацией

### Why This Matters
Pydantic Settings автоматически валидирует переменные окружения и предоставляет type-safe конфигурацию.

### Source
core/config.py:8-51

---

## Роутеры aiogram

**Category:** architecture  
**Tags:** `aiogram`, `handlers`, `architecture`  
**Created:** 2026-01-09 15:24:16

### Fact
Все handlers организованы в Router'ы для модульности

### Why This Matters
Router'ы обеспечивают чистую организацию кода и позволяют легко добавлять новые handlers.

### Source
handlers/telegram.py, handlers/admin.py

---
