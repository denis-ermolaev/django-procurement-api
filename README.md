# 1. Django Procurement API ----

REST API сервиса закупок на Django REST Framework. Проект покрывает базовый сценарий покупателя: регистрация, активация аккаунта, получение JWT, просмотр каталога, работа с корзиной, сохранение адреса доставки и подтверждение заказа.

## 1.1. Технологии ----

- Python 3.10
- Django 5.2
- Django REST Framework
- Djoser и Simple JWT
- drf-spectacular для OpenAPI/Swagger
- PostgreSQL в Docker Compose
- SQLite in-memory база для тестов
- uv для управления окружением

# 2. Быстрый старт ----

## 2.1. Подготовка окружения ----

Скопируйте пример переменных окружения:

```bash
cp .env.example .env
```

Для локального запуска оставьте `DJANGO_DEBUG=True`. Перед продовой сборкой обязательно задайте уникальный `DJANGO_SECRET_KEY`, выключите debug и заполните `DJANGO_ALLOWED_HOSTS`.

## 2.2. Запуск в Docker ----

```bash
docker compose up -d --build
make migrate
make data_to_bd
```

API будет доступен на `http://localhost:8000/`.

## 2.3. Полезные URL ----

- Swagger UI: `http://localhost:8000/api/docs/`
- OpenAPI schema: `http://localhost:8000/api/schema/`
- Django admin: `http://localhost:8000/admin/`

# 3. Переменные окружения ----

## 3.1. Обязательные переменные ----

- `DB_NAME` - имя PostgreSQL базы.
- `DB_USER` - пользователь PostgreSQL.
- `DB_PASSWORD` - пароль PostgreSQL.
- `DB_HOST` - хост PostgreSQL внутри Docker Compose, обычно `db`.
- `DB_PORT` - порт PostgreSQL, обычно `5432`.
- `DJANGO_SECRET_KEY` - секрет Django; в production обязателен.

## 3.2. Настройки Django ----

- `DJANGO_DEBUG` - `True` для разработки, `False` для production.
- `DJANGO_ALLOWED_HOSTS` - список host через запятую, например `api.example.com,localhost`.
- `DJANGO_DEFAULT_FROM_EMAIL` - отправитель сервисных писем.
- `DJANGO_ADMIN_EMAILS` - список email администраторов через запятую.

# 4. Работа с API ----

## 4.1. Регистрация и JWT ----

1. Зарегистрируйте пользователя: `POST /api/auth/users/`.
2. Возьмите `uid` и `token` из консольного письма: `docker compose logs -f web`.
3. Активируйте аккаунт: `POST /api/auth/users/activation/`.
4. Получите JWT: `POST /api/auth/jwt/create/`.
5. Передавайте access token в заголовке: `Authorization: Bearer <token>`.

Суперпользователь создается командой:

```bash
docker compose exec web python manage.py createsuperuser
```

## 4.2. Основные эндпоинты ----

- `GET /api/products/` - каталог товаров с пагинацией и фильтрами.
- `GET /api/products/{id}/` - детальная информация о предложении `ProductInfo`.
- `GET /api/basket/` - текущая корзина пользователя.
- `POST /api/basket/` - добавить предложение в корзину.
- `DELETE /api/basket/?order_id=<id>&item_id=<id>` - удалить позицию корзины.
- `GET /api/contact/` - список адресов доставки; пустой список возвращается как `{"data": []}`.
- `POST /api/contact/` - создать адрес доставки.
- `DELETE /api/contact/?id=<id>` - удалить адрес доставки.
- `POST /api/order/confirm/` - подтвердить непустую корзину.
- `GET /api/orders/` - история заказов без корзин.
- `GET /api/orders/{id}/` - заказ текущего пользователя.
- `PATCH /api/orders/{id}/` - частичное обновление заказа.

# 5. Данные и команды ----

## 5.1. Загрузка демонстрационного прайса ----

```bash
make data_to_bd
```

Команда читает `data/shop1.yaml`. Повторный запуск обновляет существующие товары, предложения и параметры без создания дублей.

## 5.2. Миграции ----

```bash
make migrate
```

Цель Makefile запускает `makemigrations api` и `migrate` внутри контейнера `web`.

# 6. Проверки качества ----

## 6.1. Тесты ----

```bash
make test_host
```

Тесты используют `core.test_settings`: in-memory SQLite, locmem email backend и быстрый password hasher.

## 6.2. Pre-commit ----

```bash
make pre-commit_host
```

Проверки включают форматирование/линтинг Ruff, mypy, ty и базовые pre-commit hooks.

# 7. Production checklist ----

## 7.1. Перед выкладкой ----

- Установить `DJANGO_DEBUG=False`.
- Задать уникальный `DJANGO_SECRET_KEY`.
- Заполнить `DJANGO_ALLOWED_HOSTS` реальными доменами.
- Проверить `DJANGO_ADMIN_EMAILS` и рабочий email backend.
- Прогнать `make test_host` и `make pre-commit_host`.
- Применить миграции на целевой базе.
- Загрузить или обновить актуальный прайс через `load_shop_data`.

## 7.2. Ограничения текущей версии ----

- Поставщик пока не управляет прайсом через API; загрузка выполняется management command.
- Email backend по умолчанию выводит письма в консоль.
- PATCH заказа сейчас разрешает только переход в статус `new`.
