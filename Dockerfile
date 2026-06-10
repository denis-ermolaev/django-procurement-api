FROM python:3.10-slim

# Отключает создание .pyc файлов и делает вывод Python "прямым"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Фиксируем версию uv
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

ENV UV_PYTHON=3.10 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Установка Python-окружения по lock-файлу
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project
ENV PATH="/opt/venv/bin:$PATH"

# Указываем порт, который будет слушать приложение
EXPOSE 8000

# Команда для запуска сервера разработки (в production позже заменим на Gunicorn)
CMD ["uv", "run", "manage.py", "runserver", "0.0.0.0:8000"]
