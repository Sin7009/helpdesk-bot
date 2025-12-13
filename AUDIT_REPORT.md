# Code Audit Report

This report summarizes technical debt, code quality issues, and security vulnerabilities identified in the codebase.

## `services/ticket_service.py`

*   **[HIGH] Security / HTML Injection**
    *   **Issue:** In `create_ticket` and `add_message_to_ticket`, `safe_user_name` is calculated using `html.escape`, but `user.full_name` (unescaped) is used directly in the formatted f-string for `admin_text`. This allows a user to inject HTML tags (e.g., links, formatting) into the admin notification.
    *   **Refactoring Action:** Replace `{user.full_name or 'Пользователь'}` with `{safe_user_name}` in the f-string.

## `handlers/telegram.py`

*   **[HIGH] Bug / Potential Crash**
    *   **Issue:** In `select_cat`, the variable `category` is used in `await state.update_data(category=category)` and in the response text, but it is **not defined**. The code defines `category_name = "Общее"`, but never assigns `category`. This will cause a `NameError`.
    *   **Refactoring Action:** Assign `category = category_name` or properly map `cat_data` to a category name before use.

*   **[MEDIUM] Logic Error**
    *   **Issue:** In `select_cat`, `category_name` is hardcoded to `"Общее"`, effectively ignoring the user's selection from `callback.data`. The menu structure exists (e.g., `cat_study`), but the logic to map these keys to names is missing.
    *   **Refactoring Action:** Create a dictionary mapping callback data (e.g., `cat_study`) to display names and look it up.

*   **[LOW] Documentation**
    *   **Issue:** `handle_text` function is complex (handling FAQ, Active Ticket, New Ticket flows) and lacks docstrings explaining the logic.
    *   **Refactoring Action:** Add a docstring explaining the three-way logic flow.

## `database/models.py`

*   **[LOW] Ghost Code**
    *   **Issue:** `SourceType.VK` is defined but unused, as the project is Telegram-only.
    *   **Refactoring Action:** Remove `VK` from the `SourceType` enum.

*   **[LOW] Outdated Comment**
    *   **Issue:** Comment `# daily_id: Integer, reset every day. Needs logic to handle this...` is outdated as the logic is now implemented in `ticket_service.py`.
    *   **Refactoring Action:** Remove the comment.

## `handlers/admin.py`

*   **[LOW] Ghost Code**
    *   **Issue:** `is_root_admin` function is defined but not used (only `is_admin_or_mod` is used).
    *   **Refactoring Action:** Remove the unused `is_root_admin` function.

## `services/scheduler.py`

*   **[LOW] Ghost Code**
    *   **Issue:** `today_end` variable is calculated but never used.
    *   **Refactoring Action:** Remove the `today_end` variable.

## `core/config.py`

*   **[LOW] Hardcoded Value**
    *   **Issue:** Database path is hardcoded as default `/app/data/support.db`.
    *   **Refactoring Action:** Consider removing default or ensuring it matches all environments, though acceptable for containerized setups.
