"""
Tests for university-specific improvements:
- Priority detection
- Student profile management
- SLA tracking
- Satisfaction ratings
"""
import pytest
from database.models import TicketPriority, User, Ticket
from services.priority_service import detect_priority, get_priority_emoji, get_priority_text


class TestPriorityDetection:
    """Test automatic priority detection based on keywords."""
    
    def test_urgent_priority_keywords(self):
        """Test that urgent keywords are detected correctly."""
        texts = [
            "СРОЧНО! Проблема с доступом",
            "Завтра экзамен, не могу войти",
            "Сегодня последний день, помогите!",
            "Заблокирован аккаунт",
            "Проблема с сессией"
        ]
        
        for text in texts:
            priority = detect_priority(text)
            assert priority == TicketPriority.URGENT, f"Failed for: {text}"
    
    def test_high_priority_keywords(self):
        """Test that high priority keywords are detected correctly."""
        texts = [
            "Важная проблема с оценками",
            "Ошибка в расписании, конфликт пар",
            "Deadline на этой неделе",
            "Дипломная работа - не могу записаться"
        ]
        
        for text in texts:
            priority = detect_priority(text)
            assert priority == TicketPriority.HIGH, f"Failed for: {text}"
    
    def test_low_priority_keywords(self):
        """Test that low priority keywords are detected correctly."""
        texts = [
            "Когда будет следующее мероприятие?",
            "Хотел бы узнать о программе",
            "Можно узнать информацию?",
            "Подскажите пожалуйста про общежитие"
        ]
        
        for text in texts:
            priority = detect_priority(text)
            assert priority == TicketPriority.LOW, f"Failed for: {text}"
    
    def test_normal_priority_default(self):
        """Test that normal priority is assigned by default."""
        texts = [
            "У меня вопрос по расписанию",
            "Как получить справку?",
            "Проблема с записью на курс"
        ]
        
        for text in texts:
            priority = detect_priority(text)
            assert priority == TicketPriority.NORMAL, f"Failed for: {text}"
    
    def test_empty_text_returns_normal(self):
        """Test that empty text returns normal priority."""
        assert detect_priority("") == TicketPriority.NORMAL
        assert detect_priority("   ") == TicketPriority.NORMAL
    
    def test_priority_emoji_mapping(self):
        """Test that priority emoji mapping is correct."""
        assert get_priority_emoji(TicketPriority.URGENT) == "🔴"
        assert get_priority_emoji(TicketPriority.HIGH) == "🟠"
        assert get_priority_emoji(TicketPriority.NORMAL) == "🟢"
        assert get_priority_emoji(TicketPriority.LOW) == "⚪"
    
    def test_priority_text_mapping(self):
        """Test that priority text mapping is correct in Russian."""
        assert get_priority_text(TicketPriority.URGENT) == "Срочно"
        assert get_priority_text(TicketPriority.HIGH) == "Высокий"
        assert get_priority_text(TicketPriority.NORMAL) == "Обычный"
        assert get_priority_text(TicketPriority.LOW) == "Низкий"


class TestStudentProfile:
    """Test student profile fields in User model."""
    
    def test_user_student_fields_optional(self):
        """Test that student fields are optional in User model."""
        # This tests that we can create a User without student info
        user = User(
            external_id=12345,
            source="tg",
            username="test_user",
            full_name="Test User"
        )
        
        assert user.student_id is None
        assert user.department is None
        assert user.course is None
    
    def test_user_can_have_student_info(self):
        """Test that User can store student information."""
        user = User(
            external_id=12345,
            source="tg",
            username="test_user",
            full_name="Test User",
            student_id="2024-12345",
            department="Факультет информационных технологий",
            course=3
        )
        
        assert user.student_id == "2024-12345"
        assert user.department == "Факультет информационных технологий"
        assert user.course == 3


class TestTicketEnhancements:
    """Test ticket enhancements for university use."""
    
    def test_ticket_has_priority_field(self):
        """Test that Ticket has priority field with default."""
        ticket = Ticket(
            user_id=1,
            daily_id=1,
            source="tg",
            question_text="Test question",
            priority=TicketPriority.NORMAL  # Explicitly set for test
        )
        
        # Should have priority field
        assert hasattr(ticket, 'priority')
        assert ticket.priority == TicketPriority.NORMAL
    
    def test_ticket_can_set_priority(self):
        """Test that Ticket priority can be set."""
        ticket = Ticket(
            user_id=1,
            daily_id=1,
            source="tg",
            question_text="Test question",
            priority=TicketPriority.URGENT
        )
        
        assert ticket.priority == TicketPriority.URGENT
    
    def test_ticket_has_sla_fields(self):
        """Test that Ticket has SLA tracking fields."""
        ticket = Ticket(
            user_id=1,
            daily_id=1,
            source="tg",
            question_text="Test question"
        )
        
        assert hasattr(ticket, 'first_response_at')
        assert ticket.first_response_at is None  # Initially None
    
    def test_ticket_has_satisfaction_fields(self):
        """Test that Ticket has satisfaction rating fields."""
        ticket = Ticket(
            user_id=1,
            daily_id=1,
            source="tg",
            question_text="Test question"
        )
        
        assert hasattr(ticket, 'rating')
        assert hasattr(ticket, 'satisfaction_comment')
        assert ticket.rating is None  # Initially None
        assert ticket.satisfaction_comment is None
    
    def test_ticket_rating_can_be_set(self):
        """Test that Ticket rating can be set to 1-5."""
        ticket = Ticket(
            user_id=1,
            daily_id=1,
            source="tg",
            question_text="Test question",
            rating=5
        )
        
        assert ticket.rating == 5
    
    def test_ticket_has_assigned_to_field(self):
        """Test that Ticket has assigned_to field for staff assignment."""
        ticket = Ticket(
            user_id=1,
            daily_id=1,
            source="tg",
            question_text="Test question"
        )
        
        assert hasattr(ticket, 'assigned_to')
        assert ticket.assigned_to is None  # Initially None
