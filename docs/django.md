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

Корзина хранится как заказ в статусе `basket`. Клиент не передает `order_id` при добавлении товара: API выбирает первый открытый `basket`-заказ текущего пользователя или создает новый. Такой выбор оставляет поведение стабильным даже если в старой базе остались несколько открытых корзин.

Добавление товара проверяет остаток `ProductInfo.quantity`, а подтверждение заказа возможно только при наличии хотя бы одной позиции. Повторное добавление того же `ProductInfo` увеличивает `OrderItem.quantity`, а не создает дубль позиции.

Удаление позиции выполняется по `OrderItem.id`. Это важно, потому что один и тот же `ProductInfo` может встречаться в разных заказах разных пользователей.

## 4.3. Контакты ----

Список контактов всегда возвращает `200`. Если адресов нет, ответ имеет вид:

```json
{"data": []}
```

## 4.4. Каталог ----

В проекте разделены общий товар и предложение магазина:

- `Product` - товар каталога без цены и остатка.
- `ProductInfo` - предложение конкретного магазина по этому товару, включая цену, остаток и рекомендованную цену.
- `ProductParameter` - характеристики предложения. Фильтр `parameter` работает именно через `ProductInfo`, потому что характеристики могут отличаться у предложений разных магазинов.

## 4.5. Заказы ----

`GET /api/orders/` возвращает историю без корзин и краткую сумму заказа. `GET /api/orders/{id}/` возвращает детальный состав заказа, включая `items` и `total_sum`. Статус `basket` нельзя выставить через `PATCH /api/orders/{id}/`, потому что возврат оформленного заказа обратно в корзину требует отдельной бизнес-операции.

## 4.6. Документация API ----

OpenAPI-описания находятся рядом с view-классами в `api/views.py`, а help text для полей - в `api/serializers.py`. После изменения публичного API обязательно запускайте:

```bash
make schema_validate_host
```
