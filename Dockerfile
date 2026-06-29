FROM python:3.10-slim

# 1. Python runtime ----
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 2. Рабочая директория ----
WORKDIR /app

# 3. Прокси для сборки (передаётся через build args) ----
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

# 4. Зависимости ----
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /uvx /bin/

ENV UV_PYTHON=3.10 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project
ENV PATH="/opt/venv/bin:$PATH"

# 5. Исходный код ----
COPY . .

# 6. Запуск ----
EXPOSE 8000

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]
