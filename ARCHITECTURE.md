# 1. Назначение ARCHITECTURE.md ----

Этот файл описывает техническую архитектуру проекта для AI-агента Codex.
Перед крупными изменениями используй его вместе с `DOMAIN.md`, `AGENTS.md`,
`README.md` и `docs/`.

Главная цель архитектуры: сохранить Django API читаемым. HTTP-слой должен быть
тонким, бизнес-логика должна жить в сервисах, OpenAPI-схемы не должны
раздувать view-классы.

# 2. Технологический стек ----

- Python 3.10.
- Django 5.2.
- Django REST Framework.
- Djoser для регистрации и активации пользователей.
- Simple JWT для JWT-аутентификации.
- drf-spectacular для OpenAPI и Swagger UI.
- django-filter для фильтров каталога.
- PostgreSQL в Docker Compose для runtime.
- SQLite in-memory через `core.test_settings` для тестов.
- uv для запуска Python-команд.
- Ruff, mypy, ty и pre-commit для качества кода.

# 3. Главные слои приложения ----

## 3.1. Routing layer ----

Файлы:

- `core/urls.py`
- `api/urls.py`

Ответственность:

- Подключить Django admin, Djoser, JWT, Swagger/OpenAPI.
- Привязать URL к DRF view-классам.

Правило: не размещай бизнес-логику в URL-модулях.

## 3.2. HTTP layer ----

Файл:

- `api/views.py`

Ответственность:

- Принять HTTP-запрос.
- Запустить serializer входных данных.
- Вызвать сервисный слой.
- Сериализовать ответ.
- Вернуть `Response`.

Правила:

- View-классы должны оставаться тонкими.
- Не добавляй в `api/views.py` длинные ORM-запросы, бизнес-ветвления и
  OpenAPI-декораторы.
- Если метод view становится больше нескольких логических шагов, вынеси
  бизнес-операцию в `api/services/`.

## 3.3. OpenAPI layer ----

Файл:

- `api/openapi.py`

Ответственность:

- `extend_schema`-декораторы.
- `OpenApiParameter`.
- `OpenApiResponse`.
- Примеры запросов и ответов.
- Общие ответы `AUTH_REQUIRED_RESPONSE`, `NOT_FOUND_RESPONSE`,
  `VALIDATION_ERROR_RESPONSE`.

Правила:

- OpenAPI-декораторы импортируются во view-классы как готовые переменные:
  `@product_list_schema`, `@basket_add_schema` и т.п.
- При изменении публичного API обновляй `api/openapi.py`.
- После изменения схем запускай `make schema_validate_host` или `make check_host`.

## 3.4. Service layer ----

Папка:

- `api/services/`

Текущие сервисы:

- `api/services/products.py` - каталог, фильтрация товаров, получение
  предложения `ProductInfo`.
- `api/services/basket.py` - текущая корзина, получение позиций, добавление и
  удаление позиции.
- `api/services/contacts.py` - список, создание и удаление контактов доставки.
- `api/services/orders.py` - подтверждение заказа, история, детали, изменение
  статуса.
- `api/services/shop_data.py` - загрузка YAML-прайса.

Ответственность:

- Бизнес-операции.
- ORM-запросы.
- Проверки ownership и бизнес-инвариантов.
- Бизнес-логи.
- Повторно используемая логика, которую не нужно держать во view.

Правила:

- Сервис может выбрасывать DRF/Django исключения, если это уже принято в
  текущем endpoint-контракте, например `ValidationError` или `get_object_or_404`.
- Сервис не должен знать про HTTP response-формат.
- Сервис не должен сериализовать данные DRF serializer'ами.
- Сервис должен логировать бизнес-события без чувствительных данных.

## 3.5. Serialization layer ----

Файл:

- `api/serializers.py`

Ответственность:

- Валидация входных команд API.
- Сериализация моделей в ответы.
- Поле `help_text` для OpenAPI.
- Расчет простых presentation-полей вроде `total_sum`.

Правила:

- Не добавляй тяжелую бизнес-логику в serializer.
- Если serializer начинает выполнять бизнес-операцию, вынеси ее в сервис.
- Для входных команд используй отдельные `serializers.Serializer`, если они не
  являются прямым CRUD модели.

## 3.6. Data layer ----

Файл:

- `api/models.py`

Ответственность:

- Django-модели.
- Константы choices.
- `UserManager`.
- Простые `__str__`.

Правила:

- Не добавляй в модели тяжелые сценарии API.
- Не меняй схему модели без миграции.
- Если добавляешь или меняешь поле модели, проверь тесты, миграции, OpenAPI,
  serializers и документацию.

## 3.7. Filter layer ----

Файл:

- `api/filters.py`

Ответственность:

- Фильтры каталога.
- Правило, что условия по предложению магазина применяются к одному
  `ProductInfo`.

Правила:

- Не ломай инвариант совместного применения `shop_id`, `price_min`,
  `price_max`, `parameter` к одному предложению.
- При изменении фильтров добавляй регрессионные тесты для товара, который есть
  в нескольких магазинах.

## 3.8. Management commands ----

Файл:

- `api/management/commands/load_shop_data.py`

Ответственность:

- CLI-обертка над сервисом загрузки прайса.
- Чтение аргументов команды.
- Вывод stdout/stderr.

Правило: бизнес-логику management command держи в сервисе. Сейчас загрузка
прайса находится в `api/services/shop_data.py`.

# 4. Поток HTTP-запроса ----

Типовой поток:

1. Клиент отправляет запрос в endpoint `/api/...`.
2. `core/urls.py` передает запрос в `api/urls.py`.
3. `api/urls.py` выбирает DRF view-класс.
4. `api.middleware.RequestLogMiddleware` логирует итог запроса.
5. View-класс валидирует входной serializer, если он нужен.
6. View-класс вызывает сервис.
7. Сервис выполняет ORM-запросы, проверки прав, бизнес-валидацию и логи.
8. View-класс сериализует результат.
9. DRF возвращает HTTP response.

# 5. Поток загрузки YAML-прайса ----

Типовой поток:

1. Пользователь запускает `python manage.py load_shop_data <path>`.
2. Django вызывает `api.management.commands.load_shop_data.Command`.
3. Command вызывает `api.services.shop_data.load_shop_data`.
4. Сервис читает YAML, проверяет `shop`, создает или обновляет магазин.
5. Сервис создает или выбирает категории.
6. Сервис создает или обновляет `Product` и `ProductInfo`.
7. Сервис полностью заменяет параметры каждого предложения.
8. Command печатает пропущенные товары в stderr и успешный итог в stdout.

# 6. Зависимости между слоями ----

Разрешенное направление зависимостей:

```text
urls -> views -> services -> models
             -> serializers
views -> openapi
serializers -> models
openapi -> serializers
management command -> services
services -> email_service
```

Запрещенные или нежелательные зависимости:

- `models -> views`
- `models -> services`
- `serializers -> views`
- `services -> views`
- `openapi -> views`
- тяжелая бизнес-логика внутри `views`
- OpenAPI-декораторы внутри `views`

# 7. Модульная карта ----

## 7.1. Core ----

- `core/settings.py` - настройки Django, DRF, Djoser, JWT, OpenAPI, email,
  logging.
- `core/test_settings.py` - тестовая SQLite-БД, locmem email backend, быстрый
  password hasher, приглушенный console logging handler.
- `core/urls.py` - корневые URL.

## 7.2. API ----

- `api/models.py` - модели домена.
- `api/admin.py` - Django admin.
- `api/urls.py` - URL бизнес-эндпоинтов.
- `api/views.py` - тонкий HTTP-слой.
- `api/openapi.py` - OpenAPI-схемы endpoints.
- `api/serializers.py` - входные и выходные serializer'ы.
- `api/filters.py` - фильтры каталога.
- `api/middleware.py` - request-level логирование.
- `api/services/` - бизнес-операции.
- `api/management/email_service.py` - email-уведомления.
- `api/management/commands/load_shop_data.py` - CLI загрузки прайса.
- `api/tests/` - тесты публичного поведения, сервисных инвариантов и
  документации OpenAPI.

# 8. Настройки окружения ----

Основные env-переменные:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_EMAIL_BACKEND`
- `DJANGO_DEFAULT_FROM_EMAIL`
- `DJANGO_ADMIN_EMAILS`
- `DJANGO_LOG_LEVEL`
- `DJANGO_LOG_SQL`

Правила:

- При добавлении переменной обновляй `.env.example`.
- Если локальный `.env` есть, добавляй туда новую переменную сразу.
- Не коммить реальные секреты.
- Если `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY` обязателен.

# 9. Логирование ----

Конфигурация:

- `LOGGING` в `core/settings.py`.
- Основной handler - `console`.
- В Docker логи читаются через `docker compose logs -f web`.

Logger'ы:

- `api.request` - итог HTTP-запросов.
- `api.services.products` - каталог.
- `api.services.basket` - корзина.
- `api.services.contacts` - контакты.
- `api.services.orders` - заказы.
- `api.services.shop_data` - загрузка прайса.
- `api.management.email_service` - email-уведомления.
- `django.db.backends` - SQL-логи при `DJANGO_LOG_SQL=True`.

Правила:

- В новом backend-коде используй `logging.getLogger(__name__)`.
- Логи должны помогать понять ветку выполнения.
- Не логируй пароли, JWT, cookies, body, телефоны, адреса, email-адреса.
- Для разработки ставь `DJANGO_LOG_LEVEL=DEBUG`.

# 10. OpenAPI и документация ----

OpenAPI:

- Схема доступна по `/api/schema/`.
- Swagger UI доступен по `/api/docs/`.
- Описания endpoints находятся в `api/openapi.py`.
- Help text полей находится в `api/serializers.py`.

Документация:

- `README.md` - пользовательский обзор проекта, запуск, API и проверки.
- `docs/api.md` - практическая памятка по публичному API.
- `docs/django.md` - технические заметки по Django-проекту.
- `DOMAIN.md` - бизнес-правила.
- `ARCHITECTURE.md` - архитектура.
- `AGENTS.md` - правила работы Codex в проекте.

При изменении публичного API обновляй `api/openapi.py`, `docs/api.md` и при
необходимости `README.md`.

# 11. Тестирование ----

Основные команды:

```bash
make test_host
make pre-commit_host
make check_host
```

`make check_host` запускает:

- coverage tests.
- coverage report.
- coverage html.
- OpenAPI validation.
- pre-commit.

Правила:

- После изменений обязательно запускай `make pre-commit_host`.
- После изменения backend-логики запускай релевантные тесты.
- После изменения большой области запускай `make test_host`.
- Перед сдачей крупного изменения запускай `make check_host`.

# 12. Как добавлять новую бизнес-функцию ----

Рекомендуемый порядок:

1. Прочитай `DOMAIN.md` и найди бизнес-инварианты.
2. Добавь или измени сервис в `api/services/`.
3. Добавь входной serializer в `api/serializers.py`, если нужен новый формат
   запроса.
4. Добавь тонкий метод во view-класс в `api/views.py`.
5. Добавь OpenAPI-декоратор в `api/openapi.py`.
6. Добавь URL в `api/urls.py`, если endpoint новый.
7. Добавь бизнес-логи в сервис.
8. Добавь тесты на успешный сценарий, ошибки прав доступа и бизнес-ошибки.
9. Обнови документацию.
10. Запусти проверки.

# 13. Как менять существующую бизнес-функцию ----

Перед изменением:

- Найди сервис, который отвечает за сценарий.
- Найди связанные tests.
- Проверь OpenAPI-декоратор.
- Проверь, не описан ли инвариант в `DOMAIN.md`.

После изменения:

- Обнови тесты.
- Обнови `DOMAIN.md`, если поменялось бизнес-правило.
- Обнови `ARCHITECTURE.md`, если поменялась структура слоев.
- Обнови `docs/api.md`, если поменялся публичный API.

# 14. Анти-паттерны ----

Не делай так:

- Не клади бизнес-логику обратно в `api/views.py`.
- Не добавляй OpenAPI-декораторы прямо в view-классы.
- Не логируй чувствительные данные.
- Не меняй API-контракт без тестов и документации.
- Не объединяй `Product` и `ProductInfo` в одну сущность.
- Не удаляй поддержку `product_info_id` как alias для удаления корзины без
  явного решения о breaking change.
- Не включай SQL-логи в production без необходимости.
- Не пересобирай Docker-контейнеры без явного разрешения.

# 15. Минимальная карта проверки после изменений ----

Если изменен каталог:

```bash
uv run python manage.py test api.tests.test_products --settings=core.test_settings
```

Если изменена корзина:

```bash
uv run python manage.py test api.tests.test_basket --settings=core.test_settings
```

Если изменены заказы:

```bash
uv run python manage.py test api.tests.test_orders --settings=core.test_settings
```

Если изменена загрузка прайсов:

```bash
uv run python manage.py test api.tests.test_load_shop_data --settings=core.test_settings
```

Если изменены OpenAPI-схемы:

```bash
make schema_validate_host
```

После любых изменений:

```bash
make pre-commit_host
```
