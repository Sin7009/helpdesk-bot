# Agent Memories: Coding Style

This file contains agent memories related to coding style.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---

## Асинхронность

**Category:** coding_style  
**Tags:** `async`, `performance`, `aiogram`  
**Created:** 2026-01-09 15:24:16

### Fact
Все I/O операции должны быть асинхронными с использованием async/await

### Why This Matters
Проект использует aiogram 3.x и SQLAlchemy 2.0 Async. Синхронные вызовы блокируют event loop и снижают производительность.

### Source
core/config.py, services/ticket_service.py, handlers/telegram.py

---

## Type Hints

**Category:** coding_style  
**Tags:** `typing`, `code-quality`  
**Created:** 2026-01-09 15:24:16

### Fact
Type hints обязательны для всех функций и методов

### Why This Matters
Type hints улучшают читаемость кода и позволяют выявлять ошибки на этапе разработки.

### Source
services/ticket_service.py:67-77, database/models.py:35-65

---

## Обработка ошибок

**Category:** coding_style  
**Tags:** `error-handling`, `logging`, `debugging`  
**Created:** 2026-01-09 15:24:16

### Fact
Никогда не используй пустые try...except: pass блоки. Всегда логируй ошибки.

### Why This Matters
Тихие провалы скрывают проблемы и затрудняют отладку. Логирование помогает отследить ошибки в продакшене.

### Source
services/ticket_service.py, handlers/admin.py

---
