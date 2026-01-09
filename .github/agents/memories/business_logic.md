# Agent Memories: Business Logic

This file contains agent memories related to business logic.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---

## Priority Detection

**Category:** business_logic  
**Tags:** `tickets`, `priority`, `automation`  
**Created:** 2026-01-09 15:24:16

### Fact
Приоритет тикета определяется автоматически по ключевым словам в тексте вопроса

### Why This Matters
Автоматическое определение приоритета помогает администраторам быстрее реагировать на срочные запросы.

### Source
services/priority_service.py, services/ticket_service.py

---

## FAQ Кэширование

**Category:** business_logic  
**Tags:** `faq`, `performance`, `caching`  
**Created:** 2026-01-09 15:24:16

### Fact
FAQ система использует in-memory кэш для быстрого поиска. Кэш загружается при старте бота.

### Why This Matters
Кэширование FAQ ускоряет поиск ответов и снижает нагрузку на БД. Для коллекций до 100 элементов простой поиск быстрее regex.

### Source
services/faq_service.py:15-30

---
