"""
Priority detection service for automatically determining ticket priority 
based on keywords and context for a university helpdesk bot.
"""
from database.models import TicketPriority

# Keywords that indicate urgent priority
URGENT_KEYWORDS = [
    "срочно", "urgent", "экзамен", "завтра", "сегодня", "не могу войти",
    "не работает личный кабинет", "заблокирован", "потерял пропуск",
    "сессия", "аккредитация", "отчисление", "стипендия не пришла"
]

# Keywords that indicate high priority
HIGH_KEYWORDS = [
    "важно", "скоро", "на этой неделе", "через пару дней", 
    "проблема с оценками", "ошибка в расписании", "конфликт пар",
    "не могу записаться", "дипломная работа", "deadline"
]

# Keywords that indicate low priority
LOW_KEYWORDS = [
    "когда будет", "планируется ли", "вопрос", "интересно",
    "можно узнать", "подскажите", "хотел бы узнать"
]

def detect_priority(text: str, category_name: str = None) -> TicketPriority:
    """
    Automatically detect ticket priority based on text content and category.
    
    Args:
        text: The ticket text content
        category_name: Optional category name for context
        
    Returns:
        TicketPriority enum value (URGENT, HIGH, NORMAL, or LOW)
    """
    if not text:
        return TicketPriority.NORMAL
    
    text_lower = text.lower()
    
    # Check for urgent keywords
    for keyword in URGENT_KEYWORDS:
        if keyword in text_lower:
            return TicketPriority.URGENT
    
    # Check for high priority keywords
    for keyword in HIGH_KEYWORDS:
        if keyword in text_lower:
            return TicketPriority.HIGH
    
    # Check for low priority keywords
    for keyword in LOW_KEYWORDS:
        if keyword in text_lower:
            return TicketPriority.LOW
    
    # Category-based priority (some categories are inherently more urgent)
    if category_name:
        category_lower = category_name.lower()
        if "it" in category_lower or "лк" in category_lower:
            # IT issues often need faster response
            return TicketPriority.HIGH
    
    # Default to normal priority
    return TicketPriority.NORMAL

def get_priority_emoji(priority: TicketPriority) -> str:
    """
    Get emoji representation for priority level.
    
    Args:
        priority: TicketPriority enum value
        
    Returns:
        Emoji string representing the priority
    """
    emoji_map = {
        TicketPriority.URGENT: "🔴",
        TicketPriority.HIGH: "🟠",
        TicketPriority.NORMAL: "🟢",
        TicketPriority.LOW: "⚪"
    }
    return emoji_map.get(priority, "🟢")

def get_priority_text(priority: TicketPriority) -> str:
    """
    Get human-readable text for priority level in Russian.
    
    Args:
        priority: TicketPriority enum value
        
    Returns:
        Russian text description of the priority
    """
    text_map = {
        TicketPriority.URGENT: "Срочно",
        TicketPriority.HIGH: "Высокий",
        TicketPriority.NORMAL: "Обычный",
        TicketPriority.LOW: "Низкий"
    }
    return text_map.get(priority, "Обычный")
