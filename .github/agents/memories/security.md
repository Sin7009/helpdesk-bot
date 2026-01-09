# Agent Memories: Security

This file contains agent memories related to security.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---

## HTML Escape

**Category:** security  
**Tags:** `security`, `xss`, `html`, `telegram`  
**Created:** 2026-01-09 15:24:16

### Fact
Всегда используй html.escape() для пользовательского ввода в Telegram сообщениях с parse_mode='HTML'

### Why This Matters
Предотвращает HTML injection атаки. Пользователи могут отправлять вредоносный HTML код, который может нарушить форматирование или использоваться для атак.

### Source
services/ticket_service.py:4, handlers/telegram.py, handlers/admin.py

---
