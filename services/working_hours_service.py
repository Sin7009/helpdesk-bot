"""Service for checking working hours and handling off-hours messages."""
import datetime
import logging
from zoneinfo import ZoneInfo

from core.config import settings

logger = logging.getLogger(__name__)


def is_within_working_hours() -> bool:
    """Check if current time is within support working hours.
    
    Returns:
        True if within working hours, False otherwise
    """
    if not settings.ENABLE_WORKING_HOURS:
        return True
    
    try:
        tz = ZoneInfo(settings.SUPPORT_TIMEZONE)
    except Exception as e:
        logger.warning(f"Invalid timezone {settings.SUPPORT_TIMEZONE}, defaulting to UTC: {e}")
        tz = ZoneInfo("UTC")
    
    now = datetime.datetime.now(tz)
    current_hour = now.hour
    
    # Check if current time is within working hours
    # and if it's a weekday (0=Monday, 6=Sunday)
    is_weekday = now.weekday() < 5  # Monday-Friday
    is_working_time = settings.SUPPORT_HOURS_START <= current_hour < settings.SUPPORT_HOURS_END
    
    return is_weekday and is_working_time


def get_next_working_hours_start() -> str:
    """Get the next time when support will be available.
    
    Returns:
        Human-readable string with next available time
    """
    try:
        tz = ZoneInfo(settings.SUPPORT_TIMEZONE)
    except Exception:
        tz = ZoneInfo("UTC")
    
    now = datetime.datetime.now(tz)
    
    # If it's before working hours today and it's a weekday
    if now.weekday() < 5 and now.hour < settings.SUPPORT_HOURS_START:
        return f"сегодня в {settings.SUPPORT_HOURS_START}:00"
    
    # Find next working day
    days_ahead = 1
    next_day = now + datetime.timedelta(days=days_ahead)
    
    while next_day.weekday() >= 5:  # Skip weekends
        days_ahead += 1
        next_day = now + datetime.timedelta(days=days_ahead)
    
    if days_ahead == 1:
        return f"завтра в {settings.SUPPORT_HOURS_START}:00"
    elif days_ahead == 2:
        return f"послезавтра в {settings.SUPPORT_HOURS_START}:00"
    else:
        day_name = {
            0: "понедельник",
            1: "вторник", 
            2: "среду",
            3: "четверг",
            4: "пятницу"
        }.get(next_day.weekday(), "")
        return f"в {day_name} в {settings.SUPPORT_HOURS_START}:00"


def get_off_hours_message() -> str:
    """Get the auto-response message for off-hours.
    
    Returns:
        Message to send to users during off-hours
    """
    next_time = get_next_working_hours_start()
    
    return (
        "🕐 <b>Сейчас нерабочее время</b>\n\n"
        f"Часы работы поддержки: {settings.SUPPORT_HOURS_START}:00 - {settings.SUPPORT_HOURS_END}:00 "
        "(пн-пт, МСК)\n\n"
        "📝 <b>Ваша заявка принята!</b>\n"
        f"Мы ответим вам {next_time}.\n\n"
        "<i>Если вопрос срочный, укажите это в сообщении.</i>"
    )
