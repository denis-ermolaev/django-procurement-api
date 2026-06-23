# 1. Переменные окружения ----

Структура `.env` должна совпадать с `.env.example`. Значения в `.env` являются
локальными и не должны перетираться при обычной разработке.

## 1.1. PostgreSQL ----

- `DB_NAME` - имя базы PostgreSQL для Django.
- `DB_USER` - пользователь PostgreSQL.
- `DB_PASSWORD` - пароль пользователя PostgreSQL.
- `DB_HOST` - hostname БД. В Docker Compose используется `db`.
- `DB_PORT` - порт PostgreSQL, обычно `5432`.

Значения выдаются разработчиком окружения или задаются локально для Docker
Compose.

## 1.2. Django ----

- `DJANGO_SECRET_KEY` - секретный ключ Django. Для production должен быть
  уникальным и храниться вне репозитория.
- `DJANGO_DEBUG` - включает debug-режим. Для production должен быть `False`.
- `DJANGO_ALLOWED_HOSTS` - список разрешенных host через запятую.

## 1.3. Email ----

- `DJANGO_EMAIL_BACKEND` - backend отправки email. Для разработки удобен console
  backend.
- `DJANGO_DEFAULT_FROM_EMAIL` - адрес отправителя системных писем.
- `DJANGO_ADMIN_EMAILS` - email администраторов через запятую для уведомлений о
  заказах.

## 1.4. Логгинг ----

- `DJANGO_LOGGING_ENABLED` - главный переключатель логирования. По умолчанию
  `False`, поэтому бизнес-логи и request-логи не шумят без явного включения.
- `DJANGO_LOG_LEVEL` - уровень логов для включенных модулей:
  `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `DJANGO_LOG_MODULES` - список logger-модулей через запятую, например
  `api.services.orders,api.request`.
- `DJANGO_LOG_SQL` - включает SQL-логи `django.db.backends` на уровне `DEBUG`.

Пример локального включения логов заказов:

```env
DJANGO_LOGGING_ENABLED=True
DJANGO_LOG_LEVEL=DEBUG
DJANGO_LOG_MODULES=api.services.orders,api.request
DJANGO_LOG_SQL=False
```

Пароли, JWT, cookies, телефоны, адреса доставки и тела запросов с персональными
данными не должны попадать в логи.
