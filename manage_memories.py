#!/usr/bin/env python3
"""
CLI tool for managing agent memories.

This script provides commands to store, view, search, and manage agent memories
that help GitHub Copilot agents understand the codebase.

Usage:
    python manage_memories.py store "subject" "fact" --category coding_style
    python manage_memories.py list
    python manage_memories.py view architecture
    python manage_memories.py search "async"
    python manage_memories.py init  # Initialize with default memories
"""
import sys
import argparse
from pathlib import Path
from services.agent_memory_service import AgentMemoryService, MemoryCategory


def store_memory(args):
    """Store a new memory."""
    service = AgentMemoryService()
    
    tags = args.tags.split(",") if args.tags else []
    
    success = service.store_memory(
        subject=args.subject,
        fact=args.fact,
        category=MemoryCategory(args.category),
        citations=args.citations,
        reason=args.reason,
        tags=tags
    )
    
    if success:
        print(f"✅ Memory stored successfully in category: {args.category}")
    else:
        print("❌ Failed to store memory")
        sys.exit(1)


def list_memories(args):
    """List all memory categories."""
    service = AgentMemoryService()
    categories = service.list_categories()
    
    if not categories:
        print("No memories stored yet.")
        print("Run 'python manage_memories.py init' to initialize with default memories.")
        return
    
    print("📚 Stored memory categories:")
    for cat in categories:
        print(f"  • {cat}")
    
    print("\nUse 'python manage_memories.py view <category>' to see details.")


def view_memories(args):
    """View memories for a specific category or all categories."""
    service = AgentMemoryService()
    
    if args.category:
        try:
            category = MemoryCategory(args.category)
            content = service.get_all_memories(category=category)
        except ValueError:
            print(f"❌ Invalid category: {args.category}")
            print(f"Valid categories: {', '.join([c.value for c in MemoryCategory])}")
            sys.exit(1)
    else:
        content = service.get_all_memories()
    
    if content:
        print(content)
    else:
        print(f"No memories found for category: {args.category}")


def search_memories(args):
    """Search for memories containing a term."""
    service = AgentMemoryService()
    results = service.search_memories(args.query)
    print(results)


def init_default_memories(args):
    """Initialize with default memories about the codebase."""
    service = AgentMemoryService()
    
    default_memories = [
        {
            "subject": "Асинхронность",
            "fact": "Все I/O операции должны быть асинхронными с использованием async/await",
            "category": MemoryCategory.CODING_STYLE,
            "citations": "core/config.py, services/ticket_service.py, handlers/telegram.py",
            "reason": "Проект использует aiogram 3.x и SQLAlchemy 2.0 Async. Синхронные вызовы блокируют event loop и снижают производительность.",
            "tags": ["async", "performance", "aiogram"]
        },
        {
            "subject": "Type Hints",
            "fact": "Type hints обязательны для всех функций и методов",
            "category": MemoryCategory.CODING_STYLE,
            "citations": "services/ticket_service.py:67-77, database/models.py:35-65",
            "reason": "Type hints улучшают читаемость кода и позволяют выявлять ошибки на этапе разработки.",
            "tags": ["typing", "code-quality"]
        },
        {
            "subject": "HTML Escape",
            "fact": "Всегда используй html.escape() для пользовательского ввода в Telegram сообщениях с parse_mode='HTML'",
            "category": MemoryCategory.SECURITY,
            "citations": "services/ticket_service.py:4, handlers/telegram.py, handlers/admin.py",
            "reason": "Предотвращает HTML injection атаки. Пользователи могут отправлять вредоносный HTML код, который может нарушить форматирование или использоваться для атак.",
            "tags": ["security", "xss", "html", "telegram"]
        },
        {
            "subject": "Обработка ошибок",
            "fact": "Никогда не используй пустые try...except: pass блоки. Всегда логируй ошибки.",
            "category": MemoryCategory.CODING_STYLE,
            "citations": "services/ticket_service.py, handlers/admin.py",
            "reason": "Тихие провалы скрывают проблемы и затрудняют отладку. Логирование помогает отследить ошибки в продакшене.",
            "tags": ["error-handling", "logging", "debugging"]
        },
        {
            "subject": "SQLAlchemy 2.0",
            "fact": "Используй новый синтаксис SQLAlchemy 2.0 с Mapped[] и mapped_column()",
            "category": MemoryCategory.DATABASE,
            "citations": "database/models.py:35-100",
            "reason": "SQLAlchemy 2.0 предоставляет улучшенную типизацию и производительность. Старый стиль deprecated.",
            "tags": ["sqlalchemy", "database", "orm"]
        },
        {
            "subject": "Middleware сессии",
            "fact": "Используй DbSessionMiddleware для автоматической инъекции AsyncSession в handlers",
            "category": MemoryCategory.ARCHITECTURE,
            "citations": "middlewares/db.py, handlers/telegram.py",
            "reason": "Централизованное управление сессиями БД предотвращает утечки соединений и упрощает код handlers.",
            "tags": ["middleware", "database", "aiogram"]
        },
        {
            "subject": "Pydantic Settings",
            "fact": "Все конфигурации через Pydantic Settings с валидацией",
            "category": MemoryCategory.ARCHITECTURE,
            "citations": "core/config.py:8-51",
            "reason": "Pydantic Settings автоматически валидирует переменные окружения и предоставляет type-safe конфигурацию.",
            "tags": ["configuration", "pydantic", "env"]
        },
        {
            "subject": "pytest-asyncio",
            "fact": "Все тесты с async/await должны использовать @pytest.mark.asyncio декоратор",
            "category": MemoryCategory.TESTING,
            "citations": "tests/test_services.py, tests/test_repositories.py, pyproject.toml:38-40",
            "reason": "pytest-asyncio правильно управляет event loop для асинхронных тестов. Без декоратора тесты будут падать.",
            "tags": ["testing", "pytest", "async"]
        },
        {
            "subject": "Покрытие тестами",
            "fact": "Минимальное покрытие кода тестами: 88%",
            "category": MemoryCategory.TESTING,
            "citations": "pyproject.toml, .github/workflows/ci.yml",
            "reason": "Высокое покрытие обеспечивает уверенность в корректности кода и предотвращает регрессии.",
            "tags": ["testing", "coverage", "ci"]
        },
        {
            "subject": "Priority Detection",
            "fact": "Приоритет тикета определяется автоматически по ключевым словам в тексте вопроса",
            "category": MemoryCategory.BUSINESS_LOGIC,
            "citations": "services/priority_service.py, services/ticket_service.py",
            "reason": "Автоматическое определение приоритета помогает администраторам быстрее реагировать на срочные запросы.",
            "tags": ["tickets", "priority", "automation"]
        },
        {
            "subject": "FAQ Кэширование",
            "fact": "FAQ система использует in-memory кэш для быстрого поиска. Кэш загружается при старте бота.",
            "category": MemoryCategory.BUSINESS_LOGIC,
            "citations": "services/faq_service.py:15-30",
            "reason": "Кэширование FAQ ускоряет поиск ответов и снижает нагрузку на БД. Для коллекций до 100 элементов простой поиск быстрее regex.",
            "tags": ["faq", "performance", "caching"]
        },
        {
            "subject": "Daily ID счётчик",
            "fact": "daily_id для тикетов генерируется атомарно через DailyTicketCounter таблицу",
            "category": MemoryCategory.DATABASE,
            "citations": "database/repositories/ticket_repository.py, database/models.py:127-135",
            "reason": "Атомарный счётчик предотвращает race conditions при конкурентном создании тикетов.",
            "tags": ["tickets", "concurrency", "database"]
        },
        {
            "subject": "Docker Multi-stage",
            "fact": "Dockerfile использует multi-stage build для минимизации размера образа",
            "category": MemoryCategory.DEPLOYMENT,
            "citations": "Dockerfile",
            "reason": "Multi-stage build уменьшает размер финального образа и улучшает безопасность, исключая инструменты сборки.",
            "tags": ["docker", "deployment", "optimization"]
        },
        {
            "subject": "Alembic Миграции",
            "fact": "Используй Alembic для всех изменений схемы БД. Не изменяй models.py без создания миграции.",
            "category": MemoryCategory.DATABASE,
            "citations": "alembic/, ALEMBIC_GUIDE.md",
            "reason": "Alembic обеспечивает контролируемые и обратимые изменения схемы БД, критично для продакшена.",
            "tags": ["database", "migrations", "alembic"]
        },
        {
            "subject": "Роутеры aiogram",
            "fact": "Все handlers организованы в Router'ы для модульности",
            "category": MemoryCategory.ARCHITECTURE,
            "citations": "handlers/telegram.py, handlers/admin.py",
            "reason": "Router'ы обеспечивают чистую организацию кода и позволяют легко добавлять новые handlers.",
            "tags": ["aiogram", "handlers", "architecture"]
        }
    ]
    
    print("🚀 Initializing agent memories...")
    success_count = 0
    
    for mem in default_memories:
        if service.store_memory(**mem):
            success_count += 1
            print(f"  ✅ {mem['subject']}")
        else:
            print(f"  ❌ Failed: {mem['subject']}")
    
    print(f"\n✨ Initialized {success_count}/{len(default_memories)} memories")
    print("\nRun 'python manage_memories.py list' to see all categories.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage agent memories for GitHub Copilot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize with default memories
  python manage_memories.py init
  
  # Store a new memory
  python manage_memories.py store "Naming Convention" \\
    "Use snake_case for variables" \\
    --category coding_style \\
    --citations "Multiple files" \\
    --reason "Consistency across codebase" \\
    --tags "naming,style"
  
  # List all categories
  python manage_memories.py list
  
  # View specific category
  python manage_memories.py view architecture
  
  # View all memories
  python manage_memories.py view
  
  # Search memories
  python manage_memories.py search "async"
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Store command
    store_parser = subparsers.add_parser("store", help="Store a new memory")
    store_parser.add_argument("subject", help="Memory subject (1-2 words)")
    store_parser.add_argument("fact", help="The fact to remember")
    store_parser.add_argument("--category", required=True, 
                             choices=[c.value for c in MemoryCategory],
                             help="Memory category")
    store_parser.add_argument("--citations", required=True, 
                             help="Source references (files, line numbers)")
    store_parser.add_argument("--reason", required=True,
                             help="Why this is important")
    store_parser.add_argument("--tags", default="",
                             help="Comma-separated tags")
    store_parser.set_defaults(func=store_memory)
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all memory categories")
    list_parser.set_defaults(func=list_memories)
    
    # View command
    view_parser = subparsers.add_parser("view", help="View memories")
    view_parser.add_argument("category", nargs="?",
                            help="Category to view (omit for all)")
    view_parser.set_defaults(func=view_memories)
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", help="Search term")
    search_parser.set_defaults(func=search_memories)
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize default memories")
    init_parser.set_defaults(func=init_default_memories)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
