## 2024-05-23 - HTML Injection in Telegram Messages
**Vulnerability:** User input (name and message text) was directly injected into HTML-formatted Telegram messages sent to admins.
**Learning:** Even internal/admin-facing messages are vulnerable to XSS-like injection if they render HTML. Telegram's `parse_mode='HTML'` respects tags like `<b>`, `<i>`, `<a>`, which allows attackers to spoof formatting or inject malicious links.
**Prevention:** Always use `html.escape()` for any variable content inserted into a string destined for `parse_mode='HTML'`.
