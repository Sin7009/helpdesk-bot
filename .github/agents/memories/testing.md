# Agent Memories: Testing

This file contains agent memories related to testing.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---

## pytest-asyncio

**Category:** testing  
**Tags:** `testing`, `pytest`, `async`  
**Created:** 2026-01-09 15:24:16

### Fact
Все тесты с async/await должны использовать @pytest.mark.asyncio декоратор

### Why This Matters
pytest-asyncio правильно управляет event loop для асинхронных тестов. Без декоратора тесты будут падать.

### Source
tests/test_services.py, tests/test_repositories.py, pyproject.toml:38-40

---

## Покрытие тестами

**Category:** testing  
**Tags:** `testing`, `coverage`, `ci`  
**Created:** 2026-01-09 15:24:16

### Fact
Минимальное покрытие кода тестами: 88%

### Why This Matters
Высокое покрытие обеспечивает уверенность в корректности кода и предотвращает регрессии.

### Source
pyproject.toml, .github/workflows/ci.yml

---
