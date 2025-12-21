# Contributing Guide

## Разработка

### Установка для разработки

1. Клонируйте репозиторий:
```bash
git clone https://github.com/Sin7009/helpdesk-bot.git
cd helpdesk-bot
```

2. Установите зависимости через uv (рекомендуется):
```bash
# Установите uv, если еще не установлен
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установите все зависимости включая dev
uv sync --all-extras --dev
```

Или используйте pip:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov
```

3. Создайте `.env` файл:
```bash
cp .env.example .env
# Отредактируйте .env и добавьте свои токены
```

### Запуск тестов

```bash
# Все тесты
uv run pytest

# С покрытием
uv run pytest --cov=. --cov-report=term-missing

# Конкретный файл
uv run pytest tests/test_services.py -v

# С подробным выводом
uv run pytest -vv
```

### Стандарты кодирования

#### Общие принципы

1. **Async/await везде** - Все I/O операции должны быть асинхронными
2. **Type hints обязательны** - Используйте аннотации типов для всех функций
3. **Docstrings** - Документируйте публичные функции в Google Style
4. **Константы в UPPER_CASE** - `MAX_MESSAGE_LENGTH = 4096`
5. **Переменные в snake_case** - `ticket_id`, `user_name`

#### Безопасность

**КРИТИЧЕСКИ ВАЖНО**: Всегда используйте `html.escape()` для пользовательского ввода:

```python
import html

# ✅ ПРАВИЛЬНО
await bot.send_message(
    chat_id=chat_id,
    text=f"<b>Сообщение:</b> {html.escape(user_text)}",
    parse_mode="HTML"
)

# ❌ ОПАСНО - HTML-инъекция!
await bot.send_message(
    chat_id=chat_id,
    text=f"<b>Сообщение:</b> {user_text}",  # УЯЗВИМОСТЬ!
    parse_mode="HTML"
)
```

#### База данных

**SQLAlchemy 2.0 стиль:**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user(session: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

**Eager loading для отношений:**

```python
from sqlalchemy.orm import selectinload

stmt = (
    select(Ticket)
    .options(selectinload(Ticket.user), selectinload(Ticket.category))
    .where(Ticket.id == ticket_id)
)
```

### Структура тестов

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_my_feature(test_session: AsyncSession):
    """Test description."""
    # Arrange
    user = User(external_id=123, source=SourceType.TELEGRAM)
    test_session.add(user)
    await test_session.commit()
    
    # Act
    result = await my_function(test_session, user.id)
    
    # Assert
    assert result is not None
    assert result.status == "success"
```

### Pre-commit checklist

Перед созданием PR убедитесь, что:

- [ ] Все тесты проходят (`pytest`)
- [ ] Покрытие не упало ниже 88% (`pytest --cov`)
- [ ] Добавлены тесты для новой функциональности
- [ ] Код документирован (docstrings)
- [ ] HTML-escape используется для пользовательского ввода
- [ ] Type hints добавлены для новых функций
- [ ] Логирование добавлено для критических операций

## Архитектура

### Структура проекта

```
├── core/              # Ядро: конфигурация, константы, логирование
├── database/          # Модели SQLAlchemy, setup
├── handlers/          # Обработчики команд Telegram
│   ├── telegram.py    # Пользовательские хэндлеры
│   └── admin.py       # Административные хэндлеры
├── services/          # Бизнес-логика
│   ├── ticket_service.py
│   ├── user_service.py
│   ├── faq_service.py
│   └── scheduler.py
├── middlewares/       # Middleware для aiogram
├── tests/             # Тесты с pytest
└── main.py            # Точка входа
```

### Слои приложения

1. **Handlers** - Обработка сообщений Telegram, валидация входных данных
2. **Services** - Бизнес-логика, работа с БД
3. **Database** - Модели данных, миграции
4. **Core** - Общие утилиты, конфигурация

### Паттерны

#### Dependency Injection (Middleware)

```python
# Middleware автоматически инъектит session
@router.message(Command("start"))
async def cmd_start(message: types.Message, session: AsyncSession):
    # session доступна автоматически
    user = await get_or_create_user(session, message.from_user)
```

#### Service Layer

```python
# Вся бизнес-логика в services, не в handlers
async def create_ticket(session, user_id, text, ...):
    # Валидация
    if not text or not text.strip():
        raise ValueError("Empty text")
    
    # Бизнес-логика
    ticket = Ticket(...)
    session.add(ticket)
    await session.commit()
    
    return ticket
```

#### Caching (FAQ Service)

```python
# Загрузка кэша при старте
await FAQService.load_cache(session)

# Быстрый поиск без запросов к БД
faq = FAQService.find_match(user_message)
```

## Troubleshooting

### Проблемы с тестами

**ValidationError: Field required**

Создайте `.env` файл в корне проекта:
```bash
TG_BOT_TOKEN=test_token
TG_ADMIN_ID=123456789
TG_STAFF_CHAT_ID=-100123456789
```

**MissingGreenlet error**

Используйте `selectinload` для загрузки связанных объектов:
```python
stmt = select(Ticket).options(selectinload(Ticket.user))
```

### Проблемы с БД

**Database is locked**

SQLite не поддерживает concurrent writes. Для production используйте PostgreSQL.

**Миграции не применяются**

Проект не использует Alembic. Миграции выполняются вручную через скрипты:
```bash
python migrate_db.py
```

### Проблемы с Docker

**База данных теряется при перезапуске**

Убедитесь, что volume смонтирован:
```yaml
volumes:
  - ./data:/app/data
```

## Полезные команды

```bash
# Разработка
python main.py                    # Запуск бота
python init_db_script.py          # Инициализация БД
python migrate_db.py              # Миграция БД

# Тестирование
pytest                            # Все тесты
pytest -v                         # Подробный вывод
pytest --cov                      # С покрытием
pytest -k "test_ticket"           # Фильтр по имени
pytest --lf                       # Last failed

# Docker
docker-compose up -d --build      # Сборка и запуск
docker-compose logs -f            # Просмотр логов
docker-compose down               # Остановка
docker-compose exec bot bash      # Войти в контейнер

# Git
git status                        # Статус изменений
git add .                         # Добавить все файлы
git commit -m "message"           # Коммит
git push origin branch-name       # Push в удалённый репозиторий
```

## Дополнительные ресурсы

- [aiogram 3.x документация](https://docs.aiogram.dev/en/latest/)
- [SQLAlchemy 2.0 документация](https://docs.sqlalchemy.org/en/20/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [pytest документация](https://docs.pytest.org/)
