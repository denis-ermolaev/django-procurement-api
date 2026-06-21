# 1. Django notes ----

Краткая техническая памятка по проекту. Основные пользовательские инструкции находятся в [README.md](../README.md), подробные примеры API - в [api.md](api.md).

## 1.1. Создание проекта ----

Команды, с которых был создан каркас:

```bash
django-admin startproject core .
python manage.py startapp api
```

# 2. Структура проекта ----

## 2.1. Core ----

- `core/settings.py` - основные настройки проекта и переменные окружения.
- `core/test_settings.py` - настройки тестового запуска на SQLite.
- `core/urls.py` - корневой роутинг, Djoser, JWT и Swagger UI.

## 2.2. API app ----

- `api/models.py` - пользователь, каталог, контакты, заказы и позиции заказов.
- `api/serializers.py` - сериализация входных команд и ответов API.
- `api/views.py` - DRF APIView эндпоинты.
- `api/filters.py` - фильтры каталога.
- `api/management/commands/load_shop_data.py` - загрузка YAML-прайса.
- `api/tests/` - тесты публичного поведения API и management command.

# 3. Рабочие команды ----

## 3.1. Проверка соединения с БД ----

```bash
python manage.py check --database default
```

## 3.2. Миграции ----

```bash
python manage.py makemigrations api
python manage.py migrate
```

В Makefile эти операции разделены:

```bash
make makemigrations
make migrate
```

## 3.3. Суперпользователь ----

```bash
python manage.py createsuperuser
```

## 3.4. Локальные тесты ----

```bash
python manage.py test --settings=core.test_settings
```

Для полной локальной проверки перед сдачей:

```bash
make check_host
```

## 3.5. Отчет покрытия ----

```bash
coverage run manage.py test --settings=core.test_settings
coverage report
coverage html
```

В Makefile это собрано в цель `make coverage_host`. HTML-отчет создается в `htmlcov/index.html`.

## 3.6. Проверка OpenAPI ----

```bash
python manage.py spectacular --settings=core.test_settings --validate --fail-on-warn --file /tmp/procurement-openapi.yaml
```

В Makefile это собрано в цель `make schema_validate_host`. Проверка полезна перед сдачей, потому что ловит рассинхронизацию Swagger-схемы и сериализаторов.

## 3.7. Загрузка демо-магазинов ----

```bash
python manage.py load_shop_data data/shop1.yaml
python manage.py load_shop_data data/shop2.yaml
```

Команда идемпотентна: повторный запуск обновляет предложения магазина и их параметры без создания дублей.

# 4. API conventions ----

## 4.1. Аутентификация ----

Все бизнес-эндпоинты требуют JWT access token в заголовке:

```http
Authorization: Bearer <access-token>
```

## 4.2. Корзина ----

Корзина хранится как заказ в статусе `basket`. Добавление товара проверяет остаток `ProductInfo.quantity`, а подтверждение заказа возможно только при наличии хотя бы одной позиции.

## 4.3. Контакты ----

Список контактов всегда возвращает `200`. Если адресов нет, ответ имеет вид:

```json
{"data": []}
```
