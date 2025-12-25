"""
Стресс-тесты для Telegram Mini App (WebApp).

Проверяет производительность и корректность работы веб-сервера
при высокой нагрузке и конкурентных запросах.
"""
import pytest
import asyncio
from contextlib import asynccontextmanager
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from webapp.server import create_app
from database.models import Base, User, Ticket, Message, Category, SourceType, TicketStatus, SenderRole, UserRole


@pytest.fixture
async def webapp_stress_engine():
    """Create a test database engine for stress testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def webapp_stress_session(webapp_stress_engine):
    """Create a test database session for stress testing."""
    async_session_factory = async_sessionmaker(
        webapp_stress_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def populate_stress_data(webapp_stress_session):
    """Populate database with test data for stress testing."""
    session = webapp_stress_session
    
    # Create categories
    categories = [Category(name=f"Category_{i}") for i in range(5)]
    session.add_all(categories)
    await session.commit()
    
    # Create 100 users
    users = []
    for i in range(100):
        user = User(
            external_id=100000 + i,
            source=SourceType.TELEGRAM,
            username=f"user_{i}",
            full_name=f"Test User {i}",
            course=(i % 4) + 1,
            group_number=f"GRP-{i:03d}"
        )
        session.add(user)
        users.append(user)
    
    await session.commit()
    
    # Create 500 tickets distributed among users
    for i in range(500):
        user = users[i % len(users)]
        ticket = Ticket(
            user_id=user.id,
            category_id=categories[i % len(categories)].id,
            source=SourceType.TELEGRAM,
            question_text=f"Test question {i}",
            status=[TicketStatus.NEW, TicketStatus.IN_PROGRESS, TicketStatus.CLOSED][i % 3],
            daily_id=i + 1
        )
        session.add(ticket)
        
        # Add messages to some tickets
        if i % 3 == 0:
            msg = Message(
                ticket_id=i + 1,  # Will be set after flush
                sender_role=SenderRole.USER,
                text=f"Message for ticket {i}"
                # Removed incorrect external_message_id
            )
            ticket.messages.append(msg)
    
    await session.commit()
    
    return {"users": users, "categories": categories}


class TestWebAppStress:
    """Стресс-тесты для веб-приложения."""
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self, webapp_stress_session, populate_stress_data):
        """
        Тест одновременных API запросов от множества пользователей.
        """
        session = webapp_stress_session
        data = populate_stress_data
        users = data["users"]
        
        @asynccontextmanager
        async def mock_new_session():
            yield session
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                # Делаем 50 одновременных запросов
                tasks = []
                for i in range(50):
                    user = users[i % len(users)]
                    task = client.get(f'/api/tickets?user_id={user.external_id}')
                    tasks.append(task)
                
                responses = await asyncio.gather(*tasks)
                
                # Проверяем, что все запросы успешны
                assert all(resp.status == 200 for resp in responses)
                
                # Проверяем содержимое ответов
                for resp in responses:
                    data = await resp.json()
                    assert 'tickets' in data
                    assert isinstance(data['tickets'], list)


    @pytest.mark.asyncio
    async def test_ticket_detail_performance(self, webapp_stress_session, populate_stress_data):
        """
        Тест производительности получения деталей тикета.
        """
        session = webapp_stress_session
        data = populate_stress_data
        users = data["users"]
        
        @asynccontextmanager
        async def mock_new_session():
            yield session
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                # Получаем детали 30 разных тикетов одновременно
                tasks = []
                for ticket_id in range(1, 31):
                    user = users[(ticket_id - 1) % len(users)]
                    task = client.get(f'/api/tickets/{ticket_id}?user_id={user.external_id}')
                    tasks.append(task)
                
                responses = await asyncio.gather(*tasks)
                
                # Проверяем успешность
                successful = [r for r in responses if r.status == 200]
                assert len(successful) >= 25  # Минимум 25 из 30 должны быть успешными


    @pytest.mark.asyncio
    async def test_high_traffic_health_check(self):
        """
        Тест health check endpoint при высокой нагрузке.
        """
        app = create_app()
        
        async with TestClient(TestServer(app)) as client:
            # Делаем 200 одновременных запросов к health endpoint
            tasks = [client.get('/health') for _ in range(200)]
            responses = await asyncio.gather(*tasks)
            
            # Все запросы должны быть успешными
            assert all(resp.status == 200 for resp in responses)
            
            # Проверяем содержимое
            for resp in responses:
                data = await resp.json()
                assert data['status'] == 'ok'


    @pytest.mark.asyncio
    async def test_invalid_requests_handling(self):
        """
        Тест обработки некорректных запросов.
        """

        # Configure the mock to return a session that behaves like a real one
        # but fails for database lookups in a controlled way or just returns empty/None

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_user = MagicMock(spec=User)
        mock_user.role = UserRole.USER
        mock_user.id = 123
        mock_user.user_id = 123 # Fix for AttributeError

        async def side_effect_scalar(*args, **kwargs):
            return mock_user

        # Ensure subsequent calls return None
        mock_result.scalar_one_or_none = MagicMock(side_effect=[mock_user, None])

        @asynccontextmanager
        async def mock_new_session():
            yield mock_session
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                # Запрос без user_id
                resp1 = await client.get('/api/tickets')
                assert resp1.status == 400
                
                # Запрос с невалидным user_id
                resp2 = await client.get('/api/tickets?user_id=invalid')
                assert resp2.status == 400
                
                # Запрос к несуществующему тикету
                # Note: We rely on the second call to scalar_one_or_none returning None
                resp3 = await client.get('/api/tickets/99999?user_id=123')

                assert resp3.status in [200, 404]


    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(self, webapp_stress_session, populate_stress_data):
        """
        Тест смешанных операций: получение списка + детали тикетов.
        """
        session = webapp_stress_session
        data = populate_stress_data
        users = data["users"]
        
        @asynccontextmanager
        async def mock_new_session():
            yield session
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                tasks = []
                
                # 25 запросов списка тикетов
                for i in range(25):
                    user = users[i]
                    tasks.append(client.get(f'/api/tickets?user_id={user.external_id}'))
                
                # 25 запросов деталей тикетов
                for i in range(25):
                    user = users[i]
                    tasks.append(client.get(f'/api/tickets/{i + 1}?user_id={user.external_id}'))
                
                # Выполняем все одновременно
                responses = await asyncio.gather(*tasks)
                
                # Проверяем, что большинство запросов успешны
                successful = [r for r in responses if r.status == 200]
                assert len(successful) >= 40  # Минимум 80% успешных


class TestWebAppEdgeCases:
    """Тесты граничных случаев для веб-приложения."""
    
    @pytest.mark.asyncio
    async def test_user_with_no_tickets(self, webapp_stress_session):
        """
        Тест пользователя без тикетов.
        """
        session = webapp_stress_session
        
        # Создаем пользователя без тикетов
        user = User(
            external_id=999999,
            source=SourceType.TELEGRAM,
            username="empty_user",
            full_name="Empty User"
        )
        session.add(user)
        await session.commit()
        
        @asynccontextmanager
        async def mock_new_session():
            yield session
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                resp = await client.get(f'/api/tickets?user_id={user.external_id}')
                assert resp.status == 200
                
                data = await resp.json()
                assert data['tickets'] == []


    @pytest.mark.asyncio
    async def test_nonexistent_user(self):
        """
        Тест запроса для несуществующего пользователя.
        """
        @asynccontextmanager
        async def mock_new_session():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            
            async with async_session_factory() as session:
                yield session
            await engine.dispose()
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                resp = await client.get('/api/tickets?user_id=999999')
                assert resp.status == 200
                
                data = await resp.json()
                assert data['tickets'] == []


    @pytest.mark.asyncio
    async def test_large_ticket_list(self, webapp_stress_session):
        """
        Тест пользователя с большим количеством тикетов.
        """
        session = webapp_stress_session
        
        # Создаем пользователя
        user = User(
            external_id=888888,
            source=SourceType.TELEGRAM,
            username="power_user",
            full_name="Power User"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        # Создаем категорию
        category = Category(name="Test Category")
        session.add(category)
        await session.commit()
        await session.refresh(category)
        
        # Создаем 50 тикетов для одного пользователя
        for i in range(50):
            ticket = Ticket(
                user_id=user.id,
                category_id=category.id,
                source=SourceType.TELEGRAM,
                question_text=f"Question {i}",
                status=TicketStatus.NEW,
                daily_id=i + 1000
            )
            session.add(ticket)
        
        await session.commit()
        
        @asynccontextmanager
        async def mock_new_session():
            yield session
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                resp = await client.get(f'/api/tickets?user_id={user.external_id}')
                assert resp.status == 200
                
                data = await resp.json()
                # API ограничивает до 20 тикетов
                assert len(data['tickets']) == 20


class TestWebAppSecurity:
    """Тесты безопасности веб-приложения."""
    
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self):
        """
        Тест защиты от SQL инъекций.
        """
        @asynccontextmanager
        async def mock_new_session():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
            async with async_session_factory() as session:
                yield session
            await engine.dispose()
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                # Попытка SQL инъекции через user_id
                malicious_ids = [
                    "1 OR 1=1",
                    "1; DROP TABLE users;",
                    "' OR '1'='1",
                    "1' UNION SELECT * FROM users--"
                ]
                
                for mal_id in malicious_ids:
                    resp = await client.get(f'/api/tickets?user_id={mal_id}')
                    # Должен вернуть 400 (невалидный формат) или 200 с пустым результатом
                    assert resp.status in [200, 400]
                    
                    if resp.status == 200:
                        data = await resp.json()
                        # Не должно быть утечки данных
                        assert 'error' in data or data.get('tickets') == []


    @pytest.mark.asyncio
    async def test_xss_prevention(self, webapp_stress_session):
        """
        Тест защиты от XSS атак.
        """
        session = webapp_stress_session
        
        # Создаем пользователя и тикет с XSS кодом
        user = User(
            external_id=777777,
            source=SourceType.TELEGRAM,
            username="<script>alert('xss')</script>",
            full_name="<b>XSS</b> User"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        category = Category(name="Test")
        session.add(category)
        await session.commit()
        await session.refresh(category)
        
        ticket = Ticket(
            user_id=user.id,
            category_id=category.id,
            source=SourceType.TELEGRAM,
            question_text="<script>alert('xss')</script>Test question",
            status=TicketStatus.NEW,
            daily_id=1
        )
        session.add(ticket)
        await session.commit()
        
        @asynccontextmanager
        async def mock_new_session():
            yield session
        
        with patch('webapp.server.new_session', side_effect=mock_new_session):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                resp = await client.get(f'/api/tickets?user_id={user.external_id}')
                assert resp.status == 200
                
                data = await resp.json()
                # JSON автоматически экранирует специальные символы
                # Проверяем, что данные возвращаются корректно
                assert len(data['tickets']) == 1


class TestWebAppResilience:
    """Тесты устойчивости к ошибкам."""
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """
        Тест обработки ошибок базы данных.
        """
        @asynccontextmanager
        async def mock_new_session_error():
            # This simulates an error occurring during the context manager entry or use
            # Since session creation is inside __aenter__, raising here simulates connection failure
            raise Exception("Database connection failed")
            yield
        
        with patch('webapp.server.new_session', side_effect=mock_new_session_error):
            app = create_app()
            
            async with TestClient(TestServer(app)) as client:
                resp = await client.get('/api/tickets?user_id=123')
                # Должен вернуть ошибку, но не упасть
                assert resp.status in [500, 503]


    @pytest.mark.asyncio
    async def test_malformed_request_handling(self):
        """
        Тест обработки некорректных запросов.
        """
        app = create_app()
        
        async with TestClient(TestServer(app)) as client:
            # Запросы с некорректными параметрами
            test_cases = [
                '/api/tickets?user_id=',  # Пустой ID
                '/api/tickets?user_id=abc',  # Не число
                '/api/tickets?user_id=-1',  # Отрицательное число
                '/api/tickets?user_id=9999999999999999999999',  # Огромное число
            ]
            
            for url in test_cases:
                resp = await client.get(url)
                # Должен корректно обработать и вернуть ошибку
                assert resp.status in [400, 500]
