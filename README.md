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

Для локального запуска оставьте `DJANGO_DEBUG=True`. Перед продовой сборкой обязательно задайте уникальный `DJANGO_SECRET_KEY`, выключите debug и заполните `DJANGO_ALLOWED_HOSTS`. Если секрет содержит `$`, оберните значение в одинарные кавычки, чтобы Docker Compose не пытался интерполировать его как переменную.

## 2.2. Запуск в Docker ----

```bash
make compose_without_build
make migrate
make data_to_bd
```

Если контейнер еще не собран или менялись зависимости/Dockerfile, выполните разовую пересборку:

```bash
make compose_build
```

API будет доступен на `http://localhost:8000/`.

## 2.3. Полезные URL ----

- Swagger UI: `http://localhost:8000/api/docs/`
- OpenAPI schema: `http://localhost:8000/api/schema/`
- Django admin: `http://localhost:8000/admin/`

Swagger UI доступен без JWT, но защищенные API-методы требуют авторизации через кнопку `Authorize` и токен в формате `Bearer <access>`.

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
- `DJANGO_EMAIL_BACKEND` - backend отправки писем; по умолчанию консольный backend Django.
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

Подробный API guide с проверенными примерами запросов и ответов находится в [docs/api.md](docs/api.md).

- `GET /api/products/` - каталог товаров с пагинацией и фильтрами.
- `GET /api/products/{id}/` - детальная информация о предложении `ProductInfo`.
- `GET /api/basket/` - текущая корзина пользователя.
- `POST /api/basket/` - добавить предложение в корзину.
- `DELETE /api/basket/?item_id=<id>` - удалить позицию текущей корзины.
- `GET /api/contact/` - список адресов доставки; пустой список возвращается как `{"data": []}`.
- `POST /api/contact/` - создать адрес доставки.
- `DELETE /api/contact/?id=<id>` - удалить адрес доставки.
- `POST /api/order/confirm/` - подтвердить непустую корзину.
- `GET /api/orders/` - история заказов без корзин.
- `GET /api/orders/{id}/` - заказ текущего пользователя.
- `PATCH /api/orders/{id}/` - частичное обновление заказа.

# 5. Данные и команды ----

## 5.1. Загрузка демонстрационных прайсов ----

```bash
make data_to_bd
```

Команда читает `data/shop1.yaml` и `data/shop2.yaml`. Повторный запуск обновляет существующие товары, предложения и параметры без создания дублей.

Для точечной загрузки доступны отдельные цели:

```bash
make data_to_bd_shop1
make data_to_bd_shop2
```

Во втором прайсе есть товары, которые уже присутствуют у первого магазина. Это проверяет сценарий, где один каталоговый товар имеет несколько предложений `ProductInfo` от разных магазинов.

## 5.2. Миграции ----

```bash
make migrate
```

Цель применяет существующие миграции внутри контейнера `web`. Для создания новых миграций во время разработки используйте:

```bash
make makemigrations
```

# 6. Проверки качества ----

## 6.1. Тесты ----

```bash
make test_host
```

Тесты используют `core.test_settings`: in-memory SQLite, locmem email backend и быстрый password hasher.

Для итоговой проверки всего проекта используйте:

```bash
make check_host
```

Эта цель последовательно запускает покрытие, OpenAPI validation и pre-commit.

## 6.2. Покрытие тестами ----

```bash
make coverage_host
```

Цель запускает Django tests через `coverage`, печатает отчет в терминал и формирует HTML-отчет в `htmlcov/index.html`. Минимальный порог покрытия задан в `pyproject.toml`.

## 6.3. Pre-commit ----

```bash
make pre-commit_host
```

Проверки включают форматирование/линтинг Ruff, mypy, ty и базовые pre-commit hooks.

## 6.4. Проверка Swagger/OpenAPI ----

```bash
make schema_validate_host
```

Цель генерирует OpenAPI schema через drf-spectacular, валидирует ее и падает при предупреждениях. Временный файл схемы пишется в `/tmp/procurement-openapi.yaml`.

# 7. Production checklist ----

## 7.1. Перед выкладкой ----

- Установить `DJANGO_DEBUG=False`.
- Задать уникальный `DJANGO_SECRET_KEY`.
- Заполнить `DJANGO_ALLOWED_HOSTS` реальными доменами.
- Проверить `DJANGO_ADMIN_EMAILS` и рабочий email backend.
- Прогнать `make check_host`.
- Применить миграции на целевой базе.
- Загрузить или обновить актуальный прайс через `load_shop_data`.

## 7.2. Ограничения текущей версии ----

- Поставщик пока не управляет прайсом через API; загрузка выполняется management command.
- Email backend по умолчанию выводит письма в консоль.
