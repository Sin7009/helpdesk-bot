# Agent Memories: Deployment

This file contains agent memories related to deployment.
These memories help GitHub Copilot agents understand conventions, patterns, and important facts about this codebase.

---

## Docker Multi-stage

**Category:** deployment  
**Tags:** `docker`, `deployment`, `optimization`  
**Created:** 2026-01-09 15:24:16

### Fact
Dockerfile использует multi-stage build для минимизации размера образа

### Why This Matters
Multi-stage build уменьшает размер финального образа и улучшает безопасность, исключая инструменты сборки.

### Source
Dockerfile

---
