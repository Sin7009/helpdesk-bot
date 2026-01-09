<div align="center">

# 🎓 Telegram Support Bot

[![CI Status](https://github.com/Sin7009/helpdesk-bot/workflows/CI/badge.svg)](https://github.com/Sin7009/helpdesk-bot/actions)
[![Docker](https://github.com/Sin7009/helpdesk-bot/workflows/Docker/badge.svg)](https://github.com/Sin7009/helpdesk-bot/pkgs/container/helpdesk-bot)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![codecov](https://codecov.io/gh/Sin7009/helpdesk-bot/branch/main/graph/badge.svg)](https://codecov.io/gh/Sin7009/helpdesk-bot)

**Современный бот технической поддержки для университетов и организаций**

[🚀 Быстрый старт](#-быстрый-старт) • [📖 Документация](#-содержание) • [🤝 Вклад в проект](CONTRIBUTING.md)

</div>

---

## 📖 Содержание

- [🌟 Возможности](#-возможности)
- [🛠 Технологический стек](#-технологический-стек)
- [🚀 Быстрый старт](#-быстрый-старт)
- [⚙️ Конфигурация](#️-конфигурация)
- [📂 Архитектура проекта](#-архитектура-проекта)
- [🎯 Команды бота](#-команды-бота)
- [🎓 Функции для университетов](#-функции-для-университетов)
- [🤖 AI/LLM интеграция](#-aillm-интеграция)
- [📊 Статистика и метрики](#-статистика-и-метрики)
- [🗄 База данных и миграции](#-база-данных-и-миграции)
- [🧪 Разработка и тестирование](#-разработка-и-тестирование)
- [⚡ Стресс-тестирование](#-стресс-тестирование)
- [🐳 Docker и деплой](#-docker-и-деплой)
- [🔒 Безопасность](#-безопасность)
- [🧠 Agent Memory System](#-agent-memory-system)
- [❓ FAQ и Troubleshooting](#-faq-и-troubleshooting)
- [🗺 Roadmap](#-roadmap)
- [📚 Документация](#-документация)

---

## 🌟 Возможности

### 🔄 Как это работает

```mermaid
graph TB
    A[👨‍🎓 Студент пишет в бота] --> B{FAQ система}
    B -->|Найден ответ| C[🤖 Автоответ из FAQ]
    B -->|Не найден| D[📝 Создание тикета]
    D --> E[🤖 AI определяет приоритет]
    E --> F[📢 Уведомление в группу поддержки]
    F --> G[👨‍💼 Администратор отвечает]
    G --> H[💬 Диалог студент ↔ поддержка]
    H --> I[✅ Закрытие тикета]
    I --> J[🤖 AI генерирует резюме]
    J --> K[⭐ Студент ставит оценку]
    K --> L[📊 Статистика обновляется]
```

### Основные функции

| Функция | Описание |
|---------|----------|
| 📝 **Тикет-система** | Создание, отслеживание и управление заявками с уникальными ID |
| 🗂 **Категории** | Гибкая система категорий (Учеба, IT, Общежитие и др.) |
| 💬 **Диалоги** | Двусторонний чат между студентом и поддержкой |
| 📎 **Медиа-файлы** | Поддержка фото и документов в заявках |
| 📊 **Аналитика** | Ежедневная статистика с метриками |
| 🔔 **Уведомления** | Real-time оповещения для администраторов |

### Университетские функции

| Функция | Описание |
|---------|----------|
| 🔴 **Приоритеты** | Автоматическое определение срочности по ключевым словам |
| 👤 **Профиль студента** | Курс, группа, факультет, статус старосты |
| ⏱ **SLA метрики** | Отслеживание времени первого ответа |
| ⭐ **Оценка качества** | Система рейтинга 1-5 звезд после закрытия |
| 📈 **Расширенная статистика** | Приоритеты, SLA, средний рейтинг |

### AI/LLM возможности

| Функция | Описание |
|---------|----------|
| 📋 **Авто-резюме** | Генерация краткого итога диалога при закрытии тикета |
| 🧠 **Анализ трендов** | Еженедельный AI-анализ частых проблем для обновления FAQ |
| 💡 **Умные подсказки** | FAQ-система с автоматическими ответами |

---

## 🛠 Технологический стек

<table>
<tr>
<td><strong>Категория</strong></td>
<td><strong>Технология</strong></td>
<td><strong>Версия</strong></td>
</tr>
<tr><td>🐍 Язык</td><td><a href="https://python.org">Python</a></td><td>3.12</td></tr>
<tr><td>🤖 Telegram API</td><td><a href="https://github.com/aiogram/aiogram">aiogram</a></td><td>3.22+</td></tr>
<tr><td>🗄 ORM</td><td><a href="https://sqlalchemy.org">SQLAlchemy</a></td><td>2.0 (Async)</td></tr>
<tr><td>💾 База данных</td><td><a href="https://sqlite.org">SQLite</a> / <a href="https://www.postgresql.org">PostgreSQL</a></td><td>16+</td></tr>
<tr><td>🔄 Миграции</td><td><a href="https://alembic.sqlalchemy.org">Alembic</a></td><td>1.17+</td></tr>
<tr><td>⚙️ Конфигурация</td><td><a href="https://docs.pydantic.dev/latest/concepts/pydantic_settings/">Pydantic Settings</a></td><td>2.12+</td></tr>
<tr><td>⏰ Планировщик</td><td><a href="https://apscheduler.readthedocs.io">APScheduler</a></td><td>3.11+</td></tr>
<tr><td>🤖 LLM</td><td><a href="https://openrouter.ai">OpenRouter API</a> (Gemini Flash)</td><td>-</td></tr>
<tr><td>📱 Mini App</td><td><a href="https://docs.aiohttp.org">aiohttp</a></td><td>3.9+</td></tr>
<tr><td>📦 Менеджер пакетов</td><td><a href="https://github.com/astral-sh/uv">uv</a></td><td>latest</td></tr>
<tr><td>🧪 Тестирование</td><td><a href="https://pytest.org">pytest</a> + pytest-asyncio</td><td>9.0+</td></tr>
<tr><td>🐳 Контейнеризация</td><td><a href="https://docker.com">Docker</a> + Docker Compose</td><td>-</td></tr>
<tr><td>🔄 CI/CD</td><td><a href="https://github.com/features/actions">GitHub Actions</a></td><td>-</td></tr>
</table>

---

## 🚀 Быстрый старт

### Шаг 1: Клонирование репозитория

```bash
git clone https://github.com/Sin7009/helpdesk-bot.git
cd helpdesk-bot
```

### Шаг 2: Настройка окружения

```bash
cp .env.example .env
```

Отредактируйте `.env` файл (получить токен можно у [@BotFather](https://t.me/BotFather)):

```ini
# Обязательные переменные
TG_BOT_TOKEN=ваш_токен_телеграм
TG_ADMIN_ID=123456789           # Ваш Telegram ID
TG_STAFF_CHAT_ID=-100123456789  # ID группы для обработки заявок

# Опциональные
OPENROUTER_API_KEY=sk-or-v1-... # Для AI-функций (резюме, анализ)
LLM_MODEL_NAME=google/gemini-3-flash-preview
DB_NAME=/app/data/support.db    # Путь к БД (для Docker)
```

### Шаг 3: Запуск

#### 🐳 Вариант A: Docker (Рекомендуется)

```bash
docker-compose up -d --build
```

Посмотреть логи:
```bash
docker-compose logs -f
```

#### 🐍 Вариант B: Локально с uv (Для разработки)

```bash
# Установка uv (если не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установка зависимостей
uv sync --all-extras --dev

# Запуск бота
python main.py
```

#### 🐍 Вариант C: Локально с pip

```bash
# Создание виртуального окружения
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Установка зависимостей
pip install .

# Запуск бота
python main.py
```

---

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Обязательная | Описание | Пример |
|------------|--------------|----------|--------|
| `TG_BOT_TOKEN` | ✅ | Токен бота от @BotFather | `123456:ABC-DEF...` |
| `TG_ADMIN_ID` | ✅ | Telegram ID главного администратора | `123456789` |
| `TG_STAFF_CHAT_ID` | ✅ | ID группы для обработки заявок | `-100123456789` |
| `DB_NAME` | ❌ | Путь к файлу базы данных (SQLite) | `/app/data/support.db` |
| `DATABASE_URL` | ❌ | URL подключения к PostgreSQL | `postgresql+asyncpg://user:pass@host:5432/db` |
| `OPENROUTER_API_KEY` | ❌ | API ключ OpenRouter для LLM | `sk-or-v1-...` |
| `LLM_MODEL_NAME` | ❌ | Модель LLM для генерации | `google/gemini-3-flash-preview` |
| `SUPPORT_HOURS_START` | ❌ | Начало рабочего дня (часы) | `9` |
| `SUPPORT_HOURS_END` | ❌ | Конец рабочего дня (часы) | `18` |
| `SUPPORT_TIMEZONE` | ❌ | Временная зона поддержки | `Europe/Moscow` |
| `ENABLE_WORKING_HOURS` | ❌ | Включить проверку рабочего времени | `True` |
| `STALE_TICKET_HOURS` | ❌ | Часов до напоминания о заявке | `4` |
| `REMINDER_INTERVAL_MINUTES` | ❌ | Интервал проверки старых заявок | `60` |
| `WEBAPP_HOST` | ❌ | Хост для запуска Mini App | `0.0.0.0` |
| `WEBAPP_PORT` | ❌ | Порт для Mini App сервера | `8080` |
| `WEBAPP_URL` | ❌ | URL Mini App для кнопки в боте | `https://your-domain.com` |

> **💡 Примечание:** Если установлен `DATABASE_URL`, он используется вместо `DB_NAME`. Это позволяет легко переключаться между SQLite и PostgreSQL.

### Как получить ID чата

1. Создайте группу в Telegram
2. Добавьте бота [@RawDataBot](https://t.me/RawDataBot) в группу
3. Он покажет `chat_id` группы (для супергрупп начинается с `-100`)
4. Удалите @RawDataBot и добавьте вашего бота

---

## 📂 Архитектура проекта

```
helpdesk-bot/
├── 📁 core/                    # Ядро приложения
│   ├── config.py              # Pydantic Settings конфигурация
│   ├── constants.py           # Константы и форматирование
│   └── logger.py              # Настройка логирования
│
├── 📁 database/                # Слой базы данных
│   ├── models.py              # SQLAlchemy 2.0 модели
│   ├── setup.py               # Инициализация БД и сессии
│   └── 📁 repositories/       # Паттерн Repository
│       ├── base.py            # Базовый репозиторий
│       ├── user_repository.py
│       ├── ticket_repository.py
│       └── category_repository.py
│
├── 📁 handlers/                # Обработчики Telegram
│   ├── telegram.py            # Хендлеры для студентов
│   └── admin.py               # Хендлеры для администраторов
│
├── 📁 services/                # Бизнес-логика
│   ├── ticket_service.py      # Логика тикетов
│   ├── user_service.py        # Логика пользователей
│   ├── faq_service.py         # FAQ с кэшированием
│   ├── priority_service.py    # Определение приоритетов
│   ├── llm_service.py         # AI/LLM интеграция
│   └── scheduler.py           # APScheduler задачи
│
├── 📁 middlewares/             # Middleware aiogram
│   └── db.py                  # Инъекция сессии БД
│
├── 📁 alembic/                 # Миграции Alembic
│   ├── env.py
│   └── 📁 versions/           # Файлы миграций
│
├── 📁 tests/                   # Тесты pytest (70+ тестов)
│   ├── conftest.py            # Фикстуры
│   ├── test_services.py
│   ├── test_handlers.py
│   └── ...
│
├── 📄 main.py                  # Точка входа
├── 📄 pyproject.toml           # Конфигурация проекта
├── 📄 docker-compose.yml       # Docker конфигурация
├── 📄 Dockerfile               # Multi-stage Docker образ
└── 📄 alembic.ini              # Конфигурация Alembic
```

### Слои приложения

```
┌─────────────────────────────────────────────────────────┐
│                    Handlers Layer                        │
│         (telegram.py, admin.py - обработка команд)      │
├─────────────────────────────────────────────────────────┤
│                    Services Layer                        │
│   (ticket_service, user_service, llm_service и др.)     │
├─────────────────────────────────────────────────────────┤
│                   Repository Layer                       │
│    (user_repository, ticket_repository и др.)           │
├─────────────────────────────────────────────────────────┤
│                    Models Layer                          │
│        (SQLAlchemy models - User, Ticket, etc.)         │
├─────────────────────────────────────────────────────────┤
│                    Database Layer                        │
│              (SQLite + aiosqlite, Alembic)              │
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Команды бота

### 👨‍🎓 Для студентов

| Команда | Описание |
|---------|----------|
| `/start` | Начать работу с ботом, регистрация, выбор темы обращения |
| `/myprofile` | Посмотреть свой профиль (курс, группа, факультет) |
| `/updateprofile` | Обновить информацию профиля |

### 👨‍💼 Для администраторов

| Команда | Описание |
|---------|----------|
| `/admin` | Открыть панель управления (WebApp) |
| `/reply ID текст` | Ответить на заявку по ID |
| `/close ID` | Закрыть заявку (с генерацией резюме) |
| `/assign ID @user` | Назначить ответственного за тикет |
| `/export [дни]` | Экспорт статистики в CSV |
| `/add_category название` | Добавить новую категорию |

> **💡 Совет:** Вместо команд можно просто отвечать на сообщение бота в группе (Reply) — это самый удобный способ!

### 🖱 Интерактивные элементы

- **📂 Выбор категории** — кнопки для выбора темы (Учеба, IT, Справки, Общежитие)
- **❓ FAQ** — быстрый доступ к частым вопросам
- **📋 Мои заявки** — просмотр истории обращений
- **⭐ Оценка качества** — кнопки 1-5 звезд после закрытия заявки

---

## 🎓 Функции для университетов

### 🔴 Система приоритетов

Бот автоматически определяет приоритет заявки по ключевым словам:

| Приоритет | Эмодзи | Ключевые слова |
|-----------|--------|----------------|
| **Срочно** | 🔴 | срочно, экзамен, завтра, сегодня, не могу войти, заблокирован, сессия, отчисление |
| **Высокий** | 🟠 | важно, проблема с оценками, ошибка в расписании, дипломная работа, deadline |
| **Обычный** | 🟢 | По умолчанию для всех остальных |
| **Низкий** | ⚪ | когда будет, хотел бы узнать, можно узнать, подскажите пожалуйста |

**Пример определения:**
```
Студент: "СРОЧНО! Не могу войти в личный кабинет, завтра экзамен!"

Бот определяет: 🔴 СРОЧНО (ключевые слова: "срочно", "завтра", "экзамен")
```

### 🎓 Профиль студента

При первом обращении бот запрашивает информацию о студенте:

1. **Курс** (1-6) — выбор кнопками
2. **Группа** — текстовый ввод (например, ИВТ-201)
3. **Статус** — студент или староста

Администраторы видят контекст в каждой заявке:
```
🔴 Новый запрос №5 (ID: #123)
👤 Иван Петров
📋 ⭐ СТАРОСТА | 3 курс | Группа ИВТ-201 | ФИТ
Тема: IT | Приоритет: Срочно
Текст: Не могу войти в личный кабинет...
```

### 📸 Пример работы бота

<details>
<summary><b>Нажмите, чтобы увидеть примеры интерфейса</b></summary>

**1. Студент создает тикет:**
```
📱 Telegram (студент):
┌─────────────────────────────────────┐
│ Привет, Иван! 👋                    │
│ Выберите тему обращения:            │
│                                     │
│ [🎓 Учеба]    [📄 Справки]         │
│ [💻 IT / ЛК]  [🏠 Общежитие]       │
│ [❓ Частые вопросы]                 │
│ [📂 Мои заявки]                     │
└─────────────────────────────────────┘
```

**2. Группа поддержки получает уведомление:**
```
💬 Telegram (группа поддержки):
┌─────────────────────────────────────┐
│ 🔴 Новый запрос №5 (ID: #123)      │
│ 👤 Иван Петров (@ivanov)           │
│ 📋 ⭐ СТАРОСТА | 3 курс | ИВТ-301  │
│ 📁 Тема: IT                         │
│ 🔴 Приоритет: Срочно                │
│                                     │
│ 💬 Вопрос:                          │
│ СРОЧНО! Не могу войти в личный      │
│ кабинет, завтра экзамен!            │
│                                     │
│ ⏱ Создан: 23.12.2025 14:30         │
└─────────────────────────────────────┘
```

**3. Администратор отвечает (Reply на сообщение):**
```
💬 Telegram (группа поддержки):
┌─────────────────────────────────────┐
│ ↪️ Ответ на: Новый запрос №5       │
│                                     │
│ Добрый день! Проверьте, что вы      │
│ используете правильный логин.       │
│ Попробуйте восстановить пароль.     │
└─────────────────────────────────────┘

✅ Ответ отправлен студенту
⏱ SLA: Первый ответ за 5 минут
```

**4. Студент получает ответ:**
```
📱 Telegram (студент):
┌─────────────────────────────────────┐
│ 💬 Ответ от поддержки:              │
│                                     │
│ Добрый день! Проверьте, что вы      │
│ используете правильный логин.       │
│ Попробуйте восстановить пароль.     │
│                                     │
│ Можете продолжить диалог,           │
│ просто напишите сюда.               │
└─────────────────────────────────────┘
```

**5. После закрытия - оценка качества:**
```
📱 Telegram (студент):
┌─────────────────────────────────────┐
│ ✅ Ваш вопрос решен. Диалог закрыт. │
│                                     │
│ 📋 Итог:                            │
│ Студент не мог войти в личный       │
│ кабинет. Проблема решена отправкой  │
│ инструкции по восстановлению        │
│ пароля.                             │
│                                     │
│ Пожалуйста, оцените качество:       │
│ [⭐] [⭐⭐] [⭐⭐⭐] [⭐⭐⭐⭐] [⭐⭐⭐⭐⭐] │
└─────────────────────────────────────┘
```

</details>

### ⭐ Оценка качества

После закрытия заявки студент получает запрос на оценку:

```
✅ Ваш вопрос решен. Диалог закрыт.

Пожалуйста, оцените качество помощи:
[⭐] [⭐⭐] [⭐⭐⭐] [⭐⭐⭐⭐] [⭐⭐⭐⭐⭐]
```

- Оценки сохраняются для статистики
- При низкой оценке (1-2) администратор получает уведомление
- Средний рейтинг отображается в ежедневном отчете

---

## 🤖 AI/LLM интеграция

Бот использует [OpenRouter API](https://openrouter.ai) для интеграции с LLM (по умолчанию Google Gemini Flash).

### 📋 Автоматическое резюме

При закрытии тикета LLM анализирует диалог и генерирует краткое резюме:

```
📋 Итог:
Студент обратился с проблемой входа в личный кабинет.
Проблема была в истекшем сроке пароля.
Выслана инструкция по восстановлению доступа.
```

### 🧠 Еженедельный анализ трендов

Каждое воскресенье в 20:00 LLM анализирует закрытые тикеты и предлагает обновления FAQ:

```
🧠 Еженедельный AI-анализ поддержки
Проанализировано тикетов: 47

Проблема: Вход в личный кабинет (12 случаев)
Решение: Инструкция по восстановлению пароля через email
Рекомендуемое действие: Добавить в базу знаний
```

### ⚙️ Настройка LLM

```ini
# .env
OPENROUTER_API_KEY=sk-or-v1-ваш_ключ
LLM_MODEL_NAME=google/gemini-3-flash-preview  # или другая модель
```

> **💡 Примечание:** LLM-функции опциональны. Без API ключа бот работает полноценно, но без генерации резюме и анализа.

---

## 📊 Статистика и метрики

### Ежедневный отчет (23:59)

Каждый день администратор получает детальную статистику:

```
📊 Статистика за 22.12.2025:

Общее:
Всего запросов: 15
Закрыто: 12

По приоритетам:
🔴 Срочно: 2
🟠 Высокий: 5
🟢 Обычный: 7
⚪ Низкий: 1

Топ тем:
1. IT / ЛК: 6
2. Учеба: 5
3. Справки: 4

SLA метрики:
Среднее время ответа: 45 мин
Средняя оценка: 4.3/5 ⭐⭐⭐⭐ (10 оценок)
```

### Отслеживаемые метрики

| Метрика | Описание |
|---------|----------|
| **Время первого ответа** | Автоматически при ответе администратора |
| **Распределение по приоритетам** | Сколько заявок каждого уровня |
| **Топ категорий** | Самые популярные темы обращений |
| **Средний рейтинг** | Оценка качества от студентов |
| **Количество закрытых** | Сколько заявок решено за день |

---

## 🗄 База данных и миграции

### Поддерживаемые базы данных

| База данных | Драйвер | Рекомендация |
|-------------|---------|--------------|
| **SQLite** | aiosqlite | Для разработки и небольших нагрузок |
| **PostgreSQL** | asyncpg | Для продакшена и высоких нагрузок |

### Модели данных

```python
# Основные модели
User          # Пользователи (студенты, модераторы, админы)
Ticket        # Заявки с приоритетами, SLA, рейтингами
Message       # Сообщения в тикетах (текст, фото, документы)
Category      # Категории заявок
FAQ           # База знаний для автоответов
DailyTicketCounter  # Атомарный счетчик daily_id
```

### Миграции с Alembic

Проект использует Alembic для управления схемой БД:

```bash
# Применить все миграции
alembic upgrade head

# Создать новую миграцию
alembic revision --autogenerate -m "Add new field"

# Посмотреть текущую версию
alembic current

# Откатить на одну версию назад
alembic downgrade -1
```

> 📖 **Подробнее:** [ALEMBIC_GUIDE.md](ALEMBIC_GUIDE.md)

### PostgreSQL (Продакшен)

Для использования PostgreSQL:

1. Запустите PostgreSQL (Docker или установленный):
```bash
docker run -d --name postgres \
  -e POSTGRES_USER=helpdesk \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=helpdesk \
  -p 5432:5432 \
  postgres:16-alpine
```

2. Установите переменную окружения:
```bash
DATABASE_URL=postgresql+asyncpg://helpdesk:your_password@localhost:5432/helpdesk
```

3. Или используйте готовый docker-compose:
```bash
docker-compose -f docker-compose.postgres.yml up -d
```

### Ручная миграция (legacy)

Для совместимости сохранен скрипт миграции:

```bash
python migrate_university_improvements.py
```

---

## 📱 Telegram Mini App

Бот поддерживает Telegram Mini App для просмотра заявок через веб-интерфейс.

### Настройка

1. Разверните веб-сервер (см. docker-compose.yml)
2. Настройте HTTPS (требуется для Mini App)
3. Установите переменные окружения:
```ini
WEBAPP_URL=https://your-domain.com
WEBAPP_PORT=8080
```

4. Зарегистрируйте Mini App в @BotFather:
   - Отправьте `/newapp`
   - Укажите URL: `https://your-domain.com/webapp/tickets`

### Функции Mini App

- 📂 Просмотр списка заявок
- 🔍 Детали заявки с историей сообщений
- ⭐ Отображение рейтинга и резюме
- 🎨 Адаптивный интерфейс под тему Telegram

---

## 🧪 Разработка и тестирование

### Установка для разработки

```bash
# Клонирование
git clone https://github.com/Sin7009/helpdesk-bot.git
cd helpdesk-bot

# Установка зависимостей (включая dev)
uv sync --all-extras --dev

# Настройка окружения
cp .env.example .env
```

### 📊 Статистика тестирования

```
╔═══════════════════════════════════════════════════════════╗
║           Тестовое покрытие проекта                      ║
╠═══════════════════════════════════════════════════════════╣
║  Всего тестов:              295+                         ║
║  Покрытие кода:              >88%                        ║
║  Строк кода в тестах:        7419                        ║
║  Время выполнения:           ~15-20 секунд               ║
╚═══════════════════════════════════════════════════════════╝
```

### Типы тестов

| Категория | Количество | Файлы | Описание |
|-----------|------------|-------|----------|
| 🔹 **Юнит-тесты** | ~150 | test_services.py, test_repositories.py | Тестирование отдельных функций |
| 🔷 **Интеграционные** | ~80 | test_integration_full_workflow.py | Тестирование взаимодействия компонентов |
| ⚡ **Стресс-тесты** | ~30 | test_stress_webapp.py, test_race_condition.py | Проверка производительности |
| 🔒 **Безопасность** | ~20 | test_security_sanitization.py | XSS, SQL injection, валидация |
| 🌐 **WebApp** | ~15 | test_webapp.py | Тестирование Mini App |

### Запуск тестов

```bash
# Все тесты
uv run pytest

# С подробным выводом
uv run pytest -v

# С покрытием кода
uv run pytest --cov=. --cov-report=term-missing

# Конкретный файл
uv run pytest tests/test_services.py -v

# Фильтр по имени
uv run pytest -k "test_ticket"

# Параллельный запуск (быстрее)
uv run pytest -n auto
```

### 🎯 Интеграционные тесты

**Тест полного цикла работы:**

```python
# test_integration_full_workflow.py::test_complete_ticket_lifecycle

1. Студент создает тикет → "СРОЧНО! Не могу войти в личный кабинет"
   ✅ Приоритет автоматически установлен как URGENT
   ✅ Уведомление отправлено в группу поддержки

2. Администратор отвечает → "Проверьте логин и пароль"
   ✅ SLA метрика (first_response_at) зафиксирована
   ✅ Статус изменен на IN_PROGRESS

3. Диалог продолжается → студент уточняет проблему
   ✅ Все сообщения сохранены в БД
   ✅ Уведомления отправлены обеим сторонам

4. Администратор закрывает тикет
   ✅ AI генерирует резюме диалога
   ✅ Студент получает запрос на оценку

5. Студент ставит оценку → 5 звезд + комментарий
   ✅ Рейтинг сохранен
   ✅ Тикет полностью закрыт
```

### 🏋️ Стресс-тесты производительности

**Конкурентное создание тикетов:**

```bash
pytest tests/test_integration_full_workflow.py::TestConcurrencyAndRaceConditions -v

# Результаты:
✅ 50 тикетов созданы параллельно за 2.5 секунды
✅ Все daily_id уникальны (нет коллизий)
✅ 0 ошибок, 100% успешных операций
```

**WebApp под нагрузкой:**

```bash
pytest tests/test_stress_webapp.py::TestWebAppStress -v

# Результаты:
✅ 200 запросов /health → все 200 OK (< 10ms каждый)
✅ 50 параллельных /api/tickets → все успешны
✅ 30 одновременных /api/tickets/{id} → >83% успех
```

### CI/CD Pipeline

GitHub Actions автоматически:

- ✅ Запускает все тесты при push/PR
- ✅ Проверяет покрытие кода
- ✅ Генерирует отчеты о покрытии (Codecov)
- ✅ Кэширует зависимости uv
- ✅ Собирает и публикует Docker образ (GHCR)
- ✅ Подписывает образы с помощью Sigstore/Cosign

### Структура тестов

```
tests/
├── conftest.py                          # Общие фикстуры (mock_bot, session и др.)
├── 🔹 Юнит-тесты
│   ├── test_services.py                 # Тесты бизнес-логики
│   ├── test_repositories.py             # Тесты слоя данных
│   ├── test_handlers.py                 # Тесты обработчиков Telegram
│   └── test_admin_handlers.py           # Тесты админских команд
├── 🔷 Интеграционные тесты
│   ├── test_integration_full_workflow.py # ⭐ Полный цикл работы
│   ├── test_university_improvements.py   # Университетские функции
│   └── test_llm_service.py              # AI/LLM интеграция
├── ⚡ Стресс-тесты
│   ├── test_stress_webapp.py            # ⭐ Стресс-тесты веб-приложения
│   ├── test_race_condition.py           # Race conditions
│   └── test_daily_id_optimization.py    # Атомарность счетчиков
├── 🔒 Тесты безопасности
│   ├── test_security_sanitization.py    # HTML escape, XSS
│   └── test_input_validation.py         # Валидация ввода
└── 🌐 WebApp тесты
    ├── test_webapp.py                   # Базовые тесты API
    └── test_webapp_admin.py             # Админская панель

Всего: 30+ файлов, 295+ тестов, 7419 строк кода
```

> 📖 **Подробная документация:** См. [TESTING.md](TESTING.md) для полного руководства по тестированию

---

## ⚡ Стресс-тестирование

Бот включает **комплексное стресс-тестирование** для проверки производительности и стабильности.

### 📊 Что тестируется

#### 1. Полный цикл работы с тикетом

```
Студент → Создание тикета → Администратор отвечает →
Диалог → Закрытие → AI-резюме → Оценка качества
```

**Тест:** `test_complete_ticket_lifecycle`
- ✅ Создание тикета с определением приоритета
- ✅ SLA метрика (первый ответ)
- ✅ Генерация AI-резюме
- ✅ Система оценок

#### 2. Конкурентная нагрузка

```
50 пользователей → одновременное создание тикетов →
проверка уникальности daily_id
```

**Тесты:**
- `test_concurrent_ticket_creation` - 50 параллельных тикетов
- `test_high_load_message_processing` - 100 сообщений в одном тикете
- `test_multiple_users_concurrent_tickets` - 10 пользователей одновременно

**Результаты:**
- ✅ Все daily_id уникальны
- ✅ Нет race conditions
- ✅ 100% успешных операций

#### 3. WebApp API стресс-тесты

```
200 одновременных запросов → /health, /api/tickets →
проверка стабильности
```

**Тесты:**
- `test_concurrent_api_requests` - 50 API запросов
- `test_high_traffic_health_check` - 200 запросов health check
- `test_concurrent_mixed_operations` - смешанные операции

**Метрики:**
| Операция | Нагрузка | Результат |
|----------|----------|-----------|
| Создание тикета | 50 параллельных | ✅ 100% успех |
| API /tickets | 50 запросов | ✅ 100% успех |
| Health check | 200 запросов | ✅ 100% успех |
| Детали тикета | 30 запросов | ✅ >83% успех |

### 🔒 Тесты безопасности

- **HTML Escape** - защита от XSS атак
- **SQL Injection** - параметризованные запросы
- **Input Validation** - проверка длины и формата
- **Access Control** - проверка прав доступа

### 🚀 Запуск стресс-тестов

```bash
# Все стресс-тесты
pytest tests/test_stress_webapp.py tests/test_integration_full_workflow.py -v

# Только конкурентность
pytest -k "concurrent" -v

# С покрытием
pytest tests/test_integration_full_workflow.py --cov=services --cov=handlers
```

### 📈 Результаты

```
===================== test session starts ======================
collected 295 items / 265 deselected / 30 selected

tests/test_integration_full_workflow.py::TestFullTicketWorkflow::test_complete_ticket_lifecycle PASSED
tests/test_integration_full_workflow.py::TestFullTicketWorkflow::test_multiple_users_concurrent_tickets PASSED
tests/test_integration_full_workflow.py::TestConcurrencyAndRaceConditions::test_concurrent_ticket_creation PASSED
tests/test_stress_webapp.py::TestWebAppStress::test_concurrent_api_requests PASSED
tests/test_stress_webapp.py::TestWebAppStress::test_high_traffic_health_check PASSED

==================== 30 passed in 12.5s =======================
```

> 📖 **Подробнее:** См. [TESTING.md](TESTING.md) для полного руководства по тестированию

---

## 🐳 Docker и деплой

### Docker образ

Образ публикуется в GitHub Container Registry:

```bash
docker pull ghcr.io/sin7009/helpdesk-bot:latest
```

### docker-compose.yml

```yaml
services:
  bot:
    build: .
    container_name: helpdesk_bot
    restart: always
    env_file:
      - .env
    volumes:
      - ./data:/app/data  # Персистентность БД
    environment:
      - DB_NAME=/app/data/support.db
```

### Полезные команды

```bash
# Сборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down

# Вход в контейнер
docker-compose exec bot bash

# Перезапуск
docker-compose restart
```

### Systemd сервис

Для запуска без Docker (bare metal):

```bash
sudo cp support-bot.service /etc/systemd/system/
sudo systemctl enable support-bot
sudo systemctl start support-bot
```

---

## 🔒 Безопасность

### HTML Injection Prevention

Все пользовательские данные экранируются с помощью `html.escape()`:

```python
import html

# ✅ ПРАВИЛЬНО
await bot.send_message(
    chat_id=chat_id,
    text=f"<b>Сообщение:</b> {html.escape(user_text)}",
    parse_mode="HTML"
)
```

### Защита от атак

- ✅ **HTML escape** для всех пользовательских данных
- ✅ **Валидация ввода** (курс 1-6, рейтинг 1-5, длина текста)
- ✅ **Проверка прав доступа** для админских команд
- ✅ **Проверка владельца** при оценке тикетов
- ✅ **Логирование ошибок** вместо `except: pass`
- ✅ **Ограничение длины** сообщений (10000 символов)

### Рекомендации

1. **Никогда** не коммитьте `.env` файл
2. Используйте **сложные токены** для бота
3. Ограничьте доступ к **группе поддержки**
4. Регулярно **обновляйте зависимости**

---

## 🧠 Agent Memory System

Проект включает систему хранения памяти агентов для GitHub Copilot — структурированный способ документирования важных фактов, конвенций и паттернов кодовой базы.

### Что это такое?

Agent Memory System хранит знания о проекте в формате markdown файлов, которые помогают:
- **GitHub Copilot агентам** генерировать более точные предложения
- **Разработчикам** быстро понимать конвенции проекта
- **Команде** поддерживать консистентность кода

### Категории памяти

Memories организованы по категориям:
- 🏗 **Architecture** — архитектурные паттерны
- 📝 **Coding Style** — стиль и конвенции кода
- 🔒 **Security** — требования безопасности
- 🧪 **Testing** — паттерны тестирования
- 🚀 **Deployment** — развертывание и инфраструктура
- 💼 **Business Logic** — доменная логика
- 🗄 **Database** — паттерны работы с БД

### Быстрый старт

```bash
# Инициализация с дефолтными памятями (15+ записей)
python manage_memories.py init

# Просмотр всех категорий
python manage_memories.py list

# Просмотр конкретной категории
python manage_memories.py view security

# Поиск по ключевому слову
python manage_memories.py search "async"

# Добавление новой памяти
python manage_memories.py store \
  "Subject" "Fact about codebase" \
  --category coding_style \
  --citations "file.py:42" \
  --reason "Why this matters" \
  --tags "tag1,tag2"
```

### Примеры хранимых знаний

Система содержит важные факты, такие как:

```markdown
## HTML Escape
Fact: Всегда используй html.escape() для пользовательского 
      ввода в Telegram сообщениях с parse_mode='HTML'
Why: Предотвращает HTML injection атаки
Source: services/ticket_service.py:4, handlers/telegram.py
Tags: security, xss, html, telegram
```

```markdown
## Асинхронность
Fact: Все I/O операции должны быть асинхронными (async/await)
Why: Проект использует aiogram 3.x и SQLAlchemy 2.0 Async
Source: core/config.py, services/ticket_service.py
Tags: async, performance, aiogram
```

### Тестирование

Система включает 16 тестов с полным покрытием:

```bash
# Запуск тестов памяти
pytest tests/test_agent_memory_service.py -v

# С покрытием
pytest tests/test_agent_memory_service.py --cov=services.agent_memory_service
```

> 📖 **Подробнее:** См. [AGENT_MEMORY_GUIDE.md](.github/agents/AGENT_MEMORY_GUIDE.md)

---

## ❓ FAQ и Troubleshooting

### Частые проблемы

<details>
<summary><b>❌ ValidationError: Field required</b></summary>

Создайте `.env` файл в корне проекта с обязательными переменными:
```ini
TG_BOT_TOKEN=your_token
TG_ADMIN_ID=123456789
TG_STAFF_CHAT_ID=-100123456789
```
</details>

<details>
<summary><b>❌ MissingGreenlet error</b></summary>

Используйте `selectinload` для eager loading связей:
```python
stmt = select(Ticket).options(selectinload(Ticket.user))
```
</details>

<details>
<summary><b>❌ Database is locked</b></summary>

SQLite не поддерживает concurrent writes. Для высокой нагрузки используйте PostgreSQL.
</details>

<details>
<summary><b>❌ Бот не отвечает в группе</b></summary>

1. Убедитесь, что бот добавлен в группу как администратор
2. Проверьте `TG_STAFF_CHAT_ID` в `.env`
3. Для супергрупп ID начинается с `-100`
</details>

<details>
<summary><b>❌ LLM резюме не генерируются</b></summary>

1. Проверьте `OPENROUTER_API_KEY` в `.env`
2. Убедитесь в наличии баланса на OpenRouter
3. Проверьте логи на ошибки API
</details>

---

## 🗺 Roadmap

### ✅ Реализовано

- [x] Тикет-система с категориями
- [x] Система приоритетов по ключевым словам
- [x] Профиль студента (курс, группа, статус)
- [x] SLA метрики (время первого ответа)
- [x] Оценка качества обслуживания
- [x] AI-резюме диалогов (Gemini)
- [x] Еженедельный AI-анализ для FAQ
- [x] Поддержка фото и документов
- [x] Ежедневная статистика
- [x] Миграции Alembic
- [x] Docker + GHCR публикация
- [x] Telegram Mini App (базовый интерфейс)
- [x] Интеграция с PostgreSQL
- [x] Команда `/assign` для назначения тикетов
- [x] Рабочее время поддержки (автоответ в нерабочее время)
- [x] Напоминания о необработанных заявках
- [x] Экспорт статистики в CSV/Excel

### 🚧 В разработке

- [ ] Веб-интерфейс для администраторов (расширенный)
- [ ] Поддержка нескольких языков

### 💡 Идеи

- [ ] Интеграция с университетскими системами (ЛК, расписание)
- [ ] Чат-бот с RAG для ответов на основе базы знаний
- [ ] Мобильное приложение для администраторов

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [QUICK_START.md](QUICK_START.md) | Быстрый старт и примеры использования |
| [TESTING.md](TESTING.md) | 🧪 **Полное руководство по тестированию и стресс-тестам** |
| [AGENT_MEMORY_GUIDE.md](.github/agents/AGENT_MEMORY_GUIDE.md) | 🧠 **Система хранения памяти агентов** |
| [UNIVERSITY_IMPROVEMENTS.md](UNIVERSITY_IMPROVEMENTS.md) | Подробное руководство по университетским функциям |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Руководство для разработчиков |
| [ALEMBIC_GUIDE.md](ALEMBIC_GUIDE.md) | Работа с миграциями базы данных |
| [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md) | Краткое резюме всех улучшений |

---

## 🤝 Вклад в проект

Мы приветствуем вклад в проект! См. [CONTRIBUTING.md](CONTRIBUTING.md) для:

- Стандартов кодирования
- Процесса создания PR
- Настройки окружения для разработки
- Написания тестов

---

## 📄 Лицензия

MIT License - см. файл [LICENSE](LICENSE) для деталей.

---

<div align="center">

**Сделано с ❤️ для университетов**

[⬆️ Вернуться наверх](#-telegram-support-bot)

</div>
