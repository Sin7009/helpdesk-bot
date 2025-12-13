import re

# Format used in notifications to staff
# Example: ID: #123
TICKET_ID_PREFIX = "ID: #"

def format_ticket_id(ticket_id: int) -> str:
    """Returns the formatted ticket ID string, e.g., 'ID: #123'"""
    return f"{TICKET_ID_PREFIX}{ticket_id}"

# Regex to parse the ID from the notification
# Matches "ID: #123" or "ID: #123" (with variable whitespace)
TICKET_ID_PATTERN = r"ID:\s*#(\d+)"
