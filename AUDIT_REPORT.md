# Code Audit Report

**Date:** 2024-05-22
**Auditor:** Jules (Senior Technical Lead)
**Scope:** Structural analysis of Python codebase (Ghost Code, Documentation, TODOs, Security).

---

## `core/config.py`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[MEDIUM]** | Security | Hardcoded default `DB_NAME` path `/app/data/support.db`. | Remove default or use `tempfile` for dev/test environments. |

## `database/models.py`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[LOW]** | Ghost Code | `SourceType.VK` is unused as VK support was removed. | Remove `VK = "vk"` from Enum. |
| **[LOW]** | Ghost Code | Outdated comment block about `daily_id` logic. | Remove commented-out explanation. |

## `handlers/admin.py`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[MEDIUM]** | Maintainability | `process_reply` regex for ID extraction is duplicated/fragile. | Use `core.constants.TICKET_ID_PATTERN` for consistent matching. |
| **[LOW]** | Security/Logic | Bare `try...except: pass` in `admin_close_ticket` hides notification failures. | Log the error: `logger.warning(f"Failed to notify user: {e}")`. |
| **[LOW]** | Naming | Variable `match` in `admin_reply_native` is generic. | Rename `match` to `ticket_id_match`. |

## `handlers/telegram.py`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[LOW]** | Naming | Variable `t` in `handle_text` is vague. | Rename `t` to `new_ticket`. |

## `migrate_db.py`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[LOW]** | Ghost Code | Local import of `new_session` in `seed_categories`. | Move import to top-level. |

## `services/scheduler.py`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[LOW]** | Documentation | Ambiguous logic comment "Отвечено: M". | Clarify comment to "Count closed tickets as resolved". |

## `services/ticket_service.py`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[HIGH]** | Security/Logic | `create_ticket` swallows notification errors (Silent Failure). | Re-raise exception or implement reliable retry queue for admin alerts. |
| **[MEDIUM]** | Documentation | `create_ticket` (>50 lines) lacks a docstring. | Add Google-style docstring explaining args and side effects. |

## `.env.example`

| Severity | Category | Issue | Refactoring Action |
| :--- | :--- | :--- | :--- |
| **[LOW]** | Ghost Code | `VK_TOKEN` variable is unused. | Remove `VK_TOKEN` line. |

---
**Summary:**
The codebase is relatively clean but suffers from a critical pattern of "swallowing exceptions" in notification logic, which can lead to silent failures (tickets created but admins never notified). There is also some leftover "ghost code" from the removed VK integration.
