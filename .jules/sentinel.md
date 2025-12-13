## 2025-02-18 - HTML Injection in Telegram Bot
**Vulnerability:** User input (names, messages) was interpolated directly into HTML strings for Telegram messages.
**Learning:** Telegram's HTML parse mode is strict; unclosed tags can cause message sending to fail (DoS). Malicious users can spoof links or format.
**Prevention:** Always use `html.escape()` on any untrusted input before adding it to an f-string used with `parse_mode='HTML'`.
