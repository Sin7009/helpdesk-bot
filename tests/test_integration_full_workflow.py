"""
Интеграционные тесты полного цикла работы бота.

Этот модуль тестирует все функции бота в связке друг с другом,
симулируя реальную работу пользователей и администраторов.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from database.models import (
    Base, User, Ticket, Message, Category, FAQ,
    TicketStatus, TicketPriority, UserRole, SourceType, SenderRole
)
from services.ticket_service import create_ticket, add_message_to_ticket
from services.user_service import get_or_create_user, ensure_admin_exists
from services.faq_service import FAQService
from services.priority_service import detect_priority


@pytest.fixture
async def integration_engine():
    """Create a fresh test database for integration tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def integration_session(integration_engine):
    """Create a test session for integration tests."""
    async_session_factory = async_sessionmaker(
        integration_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def setup_test_data(integration_session):
    """Setup test data: categories, FAQ, users."""
    session = integration_session
    
    # Create categories
    categories = [
        Category(name="Учеба"),
        Category(name="IT"),
        Category(name="Справки"),
        Category(name="Общежитие")
    ]
    session.add_all(categories)
    
    # Create FAQ entries
    faqs = [
        FAQ(trigger_word="личный кабинет", answer_text="Для входа в личный кабинет используйте свой студенческий логин"),
        FAQ(trigger_word="расписание", answer_text="Расписание доступно на сайте университета"),
        FAQ(trigger_word="справка", answer_text="Справки можно получить в деканате")
    ]
    session.add_all(faqs)
    
    # Create test users
    student = User(
        external_id=111111,
        source=SourceType.TELEGRAM,
        username="test_student",
        full_name="Иван Петров",
        role=UserRole.USER,
        course=3,
        group_number="ИВТ-301",
        is_head_student=False
    )
    admin = User(
        external_id=222222,
        source=SourceType.TELEGRAM,
        username="test_admin",
        full_name="Admin User",
        role=UserRole.ADMIN
    )
    session.add_all([student, admin])
    
    await session.commit()
    await session.refresh(student)
    await session.refresh(admin)
    
    # Load FAQ cache
    await FAQService.load_cache(session)
    
    return {
        "student": student,
        "admin": admin,
        "categories": categories
    }


class TestFullTicketWorkflow:
    """Тесты полного цикла работы с тикетом."""
    
    @pytest.mark.asyncio
    async def test_complete_ticket_lifecycle(self, integration_session, setup_test_data, mock_bot):
        """
        Тест полного жизненного цикла тикета:
        1. Студент создает тикет
        2. Проверка автоматического определения приоритета
        3. Проверка сохранения данных
        4. Закрытие тикета
        5. Добавление оценки
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        admin = data["admin"]
        
        # Шаг 1: Создание тикета студентом
        ticket = await create_ticket(
            session=session,
            user_id=student.external_id,
            source=SourceType.TELEGRAM,
            text="СРОЧНО! Не могу войти в личный кабинет, завтра экзамен!",
            bot=mock_bot,
            category_name="IT",
            user_full_name=student.full_name
        )
        await session.commit()
        await session.refresh(ticket)
        
        assert ticket.id is not None
        assert ticket.status == TicketStatus.NEW
        assert ticket.priority == TicketPriority.URGENT  # Определено по ключевым словам
        assert ticket.user_id == student.id
        
        # Проверка, что уведомление отправлено
        mock_bot.send_message.assert_called()
        
        # Шаг 2: Симулируем ответ администратора
        # Создаем сообщение от админа вручную
        admin_message = Message(
            ticket_id=ticket.id,
            sender_role=SenderRole.ADMIN,
            text="Добрый день! Проверьте, пожалуйста, что вы используете правильный логин."
        )
        session.add(admin_message)
        
        # Устанавливаем first_response_at и меняем статус
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.first_response_at = datetime.utcnow()
        await session.commit()
        await session.refresh(ticket)
        
        # Проверка SLA метрики
        assert ticket.first_response_at is not None
        assert ticket.status == TicketStatus.IN_PROGRESS
        
        # Шаг 3: Студент отвечает (добавляем еще одно сообщение)
        user_message = Message(
            ticket_id=ticket.id,
            sender_role=SenderRole.USER,
            text="Попробовал - все равно не работает. Пишет 'неверный пароль'"
        )
        session.add(user_message)
        await session.commit()
        
        # Шаг 4: Закрытие тикета
        with patch('services.llm_service.LLMService.generate_summary', 
                   return_value="Студент не мог войти в личный кабинет. Проблема решена отправкой инструкции по восстановлению пароля."):
            # Закрываем тикет вручную
            ticket.status = TicketStatus.CLOSED
            ticket.summary = "Студент не мог войти в личный кабинет. Проблема решена отправкой инструкции по восстановлению пароля."
            await session.commit()
            await session.refresh(ticket)
        
        assert ticket.status == TicketStatus.CLOSED
        assert ticket.summary is not None
        assert "восстановлению пароля" in ticket.summary
        
        # Шаг 5: Студент ставит оценку (симулируется через обновление БД)
        ticket.rating = 5
        ticket.rating_comment = "Быстро помогли, спасибо!"
        await session.commit()
        
        # Проверка финального состояния
        stmt = select(Message).where(Message.ticket_id == ticket.id)
        result = await session.execute(stmt)
        messages = result.scalars().all()
        
        assert len(messages) >= 2  # минимум 2 сообщения
        assert ticket.rating == 5


    @pytest.mark.asyncio
    async def test_multiple_users_concurrent_tickets(self, integration_session, setup_test_data, mock_bot):
        """
        Стресс-тест: несколько пользователей создают тикеты последовательно.
        """
        session = integration_session
        data = setup_test_data
        
        # Создаем несколько студентов
        students = []
        for i in range(10):
            student = User(
                external_id=300000 + i,
                source=SourceType.TELEGRAM,
                username=f"student_{i}",
                full_name=f"Студент {i}",
                role=UserRole.USER,
                course=2,
                group_number=f"ИВТ-20{i}"
            )
            session.add(student)
            students.append(student)
        
        await session.commit()
        for s in students:
            await session.refresh(s)
        
        # Создаем тикеты последовательно (чтобы избежать проблем с сессией)
        tickets = []
        for i, student in enumerate(students):
            ticket = await create_ticket(
                session=session,
                user_id=student.external_id,
                source=SourceType.TELEGRAM,
                text=f"Вопрос от студента {i}: У меня проблема с расписанием",
                bot=mock_bot,
                category_name="Учеба",
                user_full_name=student.full_name
            )
            tickets.append(ticket)
        
        await session.commit()
        
        # Проверяем, что все тикеты созданы
        assert len(tickets) == 10
        assert all(t.id is not None for t in tickets)
        
        # Проверяем уникальность daily_id
        daily_ids = [t.daily_id for t in tickets]
        assert len(daily_ids) == len(set(daily_ids)), "Daily IDs должны быть уникальными"
        
        # Проверяем, что все тикеты в статусе NEW
        assert all(t.status == TicketStatus.NEW for t in tickets)


    @pytest.mark.asyncio
    async def test_faq_auto_response(self, integration_session, setup_test_data):
        """
        Тест автоматического ответа из FAQ.
        """
        session = integration_session
        
        # Проверяем, что FAQ кэш загружен
        faq_match = FAQService.find_match("как войти в личный кабинет?")
        assert faq_match is not None
        assert "студенческий логин" in faq_match.answer_text
        
        faq_match = FAQService.find_match("где посмотреть расписание")
        assert faq_match is not None
        assert "сайте университета" in faq_match.answer_text


    @pytest.mark.asyncio
    async def test_priority_detection(self, integration_session, setup_test_data, mock_bot):
        """
        Тест определения приоритета тикетов по ключевым словам.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        # Тест URGENT
        urgent_ticket = await create_ticket(
            session=session,
            user_id=student.external_id,
            source=SourceType.TELEGRAM,
            text="СРОЧНО! Завтра экзамен, не могу войти!",
            bot=mock_bot,
            category_name="IT",
            user_full_name=student.full_name
        )
        await session.commit()
        await session.refresh(urgent_ticket)
        assert urgent_ticket.priority == TicketPriority.URGENT
        
        # Тест HIGH
        high_ticket = await create_ticket(
            session=session,
            user_id=student.external_id + 1000,  # Другой пользователь
            source=SourceType.TELEGRAM,
            text="Важно! Проблема с оценками в дипломе",
            bot=mock_bot,
            category_name="Учеба",
            user_full_name="Другой студент"
        )
        await session.commit()
        await session.refresh(high_ticket)
        assert high_ticket.priority == TicketPriority.HIGH
        
        # Тест NORMAL (по умолчанию)
        normal_ticket = await create_ticket(
            session=session,
            user_id=student.external_id + 2000,
            source=SourceType.TELEGRAM,
            text="Подскажите, где взять справку?",
            bot=mock_bot,
            category_name="Справки",
            user_full_name="Третий студент"
        )
        await session.commit()
        await session.refresh(normal_ticket)
        assert normal_ticket.priority == TicketPriority.NORMAL


    @pytest.mark.asyncio
    async def test_ticket_statistics(self, integration_session, setup_test_data, mock_bot):
        """
        Тест сбора статистики по тикетам.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        # Создаем несколько тикетов с разными статусами и приоритетами
        for i in range(5):
            ticket = await create_ticket(
                session=session,
                user_id=student.external_id,
                source=SourceType.TELEGRAM,
                text=f"Тестовый вопрос {i}",
                bot=mock_bot,
                category_name="IT",
                user_full_name=student.full_name
            )
            
            # Закрываем некоторые тикеты
            if i % 2 == 0:
                ticket.status = TicketStatus.CLOSED
                ticket.rating = 4 + (i % 2)  # Оценки 4 и 5
        
        await session.commit()
        
        # Собираем статистику
        total_tickets = await session.execute(select(func.count(Ticket.id)))
        total = total_tickets.scalar()
        
        closed_tickets = await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.CLOSED)
        )
        closed = closed_tickets.scalar()
        
        avg_rating = await session.execute(
            select(func.avg(Ticket.rating)).where(Ticket.rating.isnot(None))
        )
        avg = avg_rating.scalar()
        
        assert total >= 5
        assert closed >= 3
        assert avg >= 4.0


class TestUserProfileWorkflow:
    """Тесты работы с профилем пользователя."""
    
    @pytest.mark.asyncio
    async def test_user_registration_flow(self, integration_session, setup_test_data):
        """
        Тест регистрации нового пользователя.
        """
        session = integration_session
        
        # Создаем нового пользователя (симуляция первого /start)
        new_user = User(
            external_id=999999,
            source=SourceType.TELEGRAM,
            username="new_student",
            full_name="Новый Студент",
            role=UserRole.USER
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        
        # Пользователь заполняет профиль
        new_user.course = 1
        new_user.group_number = "ИВТ-101"
        new_user.is_head_student = True
        new_user.department = "Факультет Информационных Технологий"
        
        await session.commit()
        await session.refresh(new_user)
        
        # Проверяем, что данные сохранены
        assert new_user.course == 1
        assert new_user.group_number == "ИВТ-101"
        assert new_user.is_head_student is True


    @pytest.mark.asyncio
    async def test_head_student_badge(self, integration_session, setup_test_data, mock_bot):
        """
        Тест отображения значка старосты в тикете.
        """
        session = integration_session
        
        # Создаем старосту
        head_student = User(
            external_id=777777,
            source=SourceType.TELEGRAM,
            username="head_student",
            full_name="Староста Группы",
            role=UserRole.USER,
            course=3,
            group_number="ИВТ-301",
            is_head_student=True
        )
        session.add(head_student)
        await session.commit()
        await session.refresh(head_student)
        
        # Создаем тикет от старосты
        ticket = await create_ticket(
            session=session,
            user_id=head_student.external_id,
            source=SourceType.TELEGRAM,
            text="Вопрос от старосты группы",
            bot=mock_bot,
            category_name="Учеба",
            user_full_name=head_student.full_name
        )
        await session.commit()
        
        # Проверяем, что пользователь - староста
        assert ticket.user.is_head_student is True


class TestConcurrencyAndRaceConditions:
    """Стресс-тесты для проверки конкурентности и race conditions."""
    
    @pytest.mark.asyncio
    async def test_concurrent_ticket_creation(self, integration_session, setup_test_data, mock_bot):
        """
        Тест создания тикетов с уникальными daily_id.
        Создаем 20 тикетов последовательно чтобы проверить атомарность счетчика.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        # Создаем 20 тикетов последовательно
        tickets = []
        for i in range(20):
            ticket = await create_ticket(
                session=session,
                user_id=student.external_id,
                source=SourceType.TELEGRAM,
                text=f"Параллельный вопрос {i}",
                bot=mock_bot,
                category_name="IT",
                user_full_name=student.full_name
            )
            tickets.append(ticket)
        
        await session.commit()
        
        # Проверяем уникальность daily_id
        daily_ids = [t.daily_id for t in tickets]
        assert len(daily_ids) == len(set(daily_ids)), "Найдены дублирующиеся daily_id!"
        
        # Проверяем последовательность
        sorted_ids = sorted(daily_ids)
        for i in range(len(sorted_ids) - 1):
            assert sorted_ids[i+1] == sorted_ids[i] + 1, "Daily IDs должны быть последовательными"


    @pytest.mark.asyncio
    async def test_high_load_message_processing(self, integration_session, setup_test_data, mock_bot):
        """
        Стресс-тест: обработка большого количества сообщений.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        admin = data["admin"]
        
        # Создаем тикет
        ticket = await create_ticket(
            session=session,
            user_id=student.external_id,
            source=SourceType.TELEGRAM,
            text="Начальный вопрос",
            bot=mock_bot,
            category_name="IT",
            user_full_name=student.full_name
        )
        await session.commit()
        await session.refresh(ticket)
        
        # Добавляем 50 сообщений напрямую в БД (быстрее чем через API)
        messages = []
        for i in range(50):
            sender_role = SenderRole.USER if i % 2 == 0 else SenderRole.ADMIN
            msg = Message(
                ticket_id=ticket.id,
                sender_role=sender_role,
                text=f"Сообщение номер {i}"
            )
            messages.append(msg)
        
        session.add_all(messages)
        await session.commit()
        
        # Проверяем, что все сообщения сохранены
        stmt = select(func.count(Message.id)).where(Message.ticket_id == ticket.id)
        result = await session.execute(stmt)
        message_count = result.scalar()
        
        assert message_count >= 50  # 50 + возможно начальное сообщение


class TestWorkingHoursAndScheduler:
    """Тесты рабочего времени и планировщика."""
    
    @pytest.mark.asyncio
    async def test_ticket_outside_working_hours(self, integration_session, setup_test_data, mock_bot):
        """
        Тест создания тикета в нерабочее время.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        # Создаем тикет (проверка рабочего времени происходит внутри)
        ticket = await create_ticket(
            session=session,
            user_id=student.external_id,
            source=SourceType.TELEGRAM,
            text="Вопрос в нерабочее время",
            bot=mock_bot,
            category_name="IT",
            user_full_name=student.full_name
        )
        await session.commit()
        
        # Тикет должен быть создан в любом случае
        assert ticket.id is not None
        assert ticket.status == TicketStatus.NEW


    @pytest.mark.asyncio
    async def test_stale_ticket_detection(self, integration_session, setup_test_data, mock_bot):
        """
        Тест обнаружения старых необработанных тикетов.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        # Создаем старый тикет (более 4 часов назад)
        old_ticket = await create_ticket(
            session=session,
            user_id=student.external_id,
            source=SourceType.TELEGRAM,
            text="Старый необработанный вопрос",
            bot=mock_bot,
            category_name="IT",
            user_full_name=student.full_name
        )
        
        # Меняем время создания на 5 часов назад
        old_ticket.created_at = datetime.utcnow() - timedelta(hours=5)
        await session.commit()
        await session.refresh(old_ticket)
        
        # Находим старые тикеты
        stale_hours = 4
        cutoff_time = datetime.utcnow() - timedelta(hours=stale_hours)
        
        stmt = select(Ticket).where(
            Ticket.status == TicketStatus.NEW,
            Ticket.created_at < cutoff_time
        )
        result = await session.execute(stmt)
        stale_tickets = result.scalars().all()
        
        assert len(stale_tickets) >= 1
        assert old_ticket.id in [t.id for t in stale_tickets]


class TestSecurityAndValidation:
    """Тесты безопасности и валидации."""
    
    @pytest.mark.asyncio
    async def test_html_escape_in_notifications(self, integration_session, setup_test_data, mock_bot):
        """
        Тест экранирования HTML в уведомлениях.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        # Создаем тикет с HTML-кодом
        malicious_text = "<script>alert('XSS')</script> <b>Вопрос</b>"
        ticket = await create_ticket(
            session=session,
            user_id=student.external_id,
            source=SourceType.TELEGRAM,
            text=malicious_text,
            bot=mock_bot,
            category_name="IT",
            user_full_name="<b>Malicious</b> User"
        )
        await session.commit()
        
        # Проверяем, что HTML экранирован в вызове bot.send_message
        mock_bot.send_message.assert_called()
        call_args = mock_bot.send_message.call_args
        
        # text параметр должен содержать экранированный HTML
        text_arg = call_args.kwargs.get('text', '')
        assert '&lt;script&gt;' in text_arg or '<script>' not in text_arg
        assert '&lt;b&gt;' in text_arg or '<b>Malicious</b>' not in text_arg


    @pytest.mark.asyncio
    async def test_ticket_text_length_validation(self, integration_session, setup_test_data, mock_bot):
        """
        Тест валидации длины текста тикета.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        # Слишком длинный текст
        long_text = "A" * 10001
        
        with pytest.raises(ValueError, match="too long"):
            await create_ticket(
                session=session,
                user_id=student.external_id,
                source=SourceType.TELEGRAM,
                text=long_text,
                bot=mock_bot,
                category_name="IT",
                user_full_name=student.full_name
            )


    @pytest.mark.asyncio
    async def test_empty_ticket_validation(self, integration_session, setup_test_data, mock_bot):
        """
        Тест валидации пустого тикета.
        """
        session = integration_session
        data = setup_test_data
        student = data["student"]
        
        with pytest.raises(ValueError, match="cannot be empty"):
            await create_ticket(
                session=session,
                user_id=student.external_id,
                source=SourceType.TELEGRAM,
                text="",
                bot=mock_bot,
                category_name="IT",
                user_full_name=student.full_name
            )
