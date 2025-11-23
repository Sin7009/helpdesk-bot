# Используем легкий Python 3.12
FROM python:3.12-slim-bookworm

# Устанавливаем uv (копируем бинарник из официального образа)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Настройки для Python и uv
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Сначала копируем файлы зависимостей (для кэширования Docker слоев)
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости (без самого проекта пока)
RUN uv sync --frozen --no-install-project --no-dev

# Копируем весь код проекта
COPY . .

# Доустанавливаем сам проект (если он оформлен как пакет) и прописываем путь
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# Запускаем: Сначала миграции БД, потом сам бот
CMD ["sh", "-c", "python init_db_script.py && python main.py"]
