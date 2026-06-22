# 1. Django Procurement API ----

REST API сервиса закупок на Django REST Framework. Проект покрывает ролевую модель buyer/shop/admin: покупатель работает с каталогом, корзиной, адресами и заказами; магазин управляет своими предложениями и позициями заказов; администратор модерирует магазины, каталог, предложения, пользователей и заказы.

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

## 3.3. Логгинг ----

- `DJANGO_LOG_LEVEL` - общий уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR` или `CRITICAL`.
- `DJANGO_LOG_SQL` - включает SQL-логи Django при значении `True`; по умолчанию выключено.

Для разработки удобно ставить `DJANGO_LOG_LEVEL=DEBUG`: кроме итогов HTTP-запросов будут видны бизнес-события внутри функций каталога, корзины, заказов, загрузки прайсов и отправки email.

В Docker логи Django доступны через:

```bash
docker compose logs -f web
```

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

## 4.2. Базовые термины API ----

- `Product` - общий товар каталога, например конкретная модель телефона.
- `ProductInfo` - предложение магазина по этому товару: магазин, цена, остаток, рекомендованная цена и характеристики.
- Корзина - это `Order` в статусе `basket`. При первом добавлении товара она создается автоматически.
- Позиция корзины или заказа - это `OrderItem`. Для удаления позиции используйте именно `item_id`, а не `product_info_id`.
- В историю заказов попадают только заказы, которые уже вышли из статуса `basket`.
- Покупатель работает только с корзиной, контактами и своими заказами; магазин работает со своими предложениями и позициями заказов; администратор управляет справочниками и статусами через отдельные `/api/admin/` endpoints.
- Остаток предложения резервируется при подтверждении заказа и списывается из физического остатка при отправке позиции магазином.
- Числовые инварианты предложений дополнительно защищены на уровне БД: `quantity >= 0`, `reserved_quantity >= 0`, `reserved_quantity <= quantity`, `price > 0`, `price_rrc >= 0`; у позиции заказа `quantity >= 1`.
- Административные изменения не обходят ключевые инварианты: `shop`-пользователь должен иметь связанный магазин, `admin` требует `is_staff=true`, а отправленные позиции нельзя откатить к досылочным статусам.

## 4.3. Основные эндпоинты ----

Подробный API guide с проверенными примерами запросов и ответов находится в [docs/api.md](docs/api.md).

- `GET /api/products/` - каталог товаров с пагинацией и фильтрами.
- `GET /api/products/{id}/` - детальная информация о предложении `ProductInfo`; `{id}` здесь ID предложения, не товара.
- `GET /api/basket/` - позиции текущей корзины пользователя.
- `POST /api/basket/` - добавить предложение в корзину; повторное добавление увеличивает `quantity`.
- `DELETE /api/basket/?item_id=<id>` - удалить позицию текущей корзины по ID `OrderItem`.
- `GET /api/contact/` - список адресов доставки; пустой список возвращается как `{"data": []}`.
- `POST /api/contact/` - создать адрес доставки.
- `DELETE /api/contact/?id=<id>` - удалить адрес доставки.
- `POST /api/order/confirm/` - подтвердить непустую корзину.
- `GET /api/orders/` - история заказов без корзин.
- `GET /api/orders/{id}/` - заказ текущего пользователя с позициями и итоговой суммой.
- `PATCH /api/orders/{id}/` - отменить свой заказ до начала обработки магазином.
- `POST /api/shops/register/` - зарегистрировать магазин со статусом `pending`.
- `GET|PATCH /api/shop/profile/` - профиль своего магазина.
- `GET|POST /api/shop/offers/`, `PATCH /api/shop/offers/{id}/` - предложения своего магазина.
- `GET /api/shop/order-items/`, `PATCH /api/shop/order-items/{id}/` - позиции заказов своего магазина.
- `GET|PATCH /api/admin/users/`, `/api/admin/shops/`, `/api/admin/categories/`, `/api/admin/products/`, `/api/admin/parameters/`, `/api/admin/offers/`, `/api/admin/orders/` - административные операции для `is_staff=true` и `type=admin`.

## 4.4. Swagger/OpenAPI ----

Swagger UI находится по адресу `http://localhost:8000/api/docs/`. В описании endpoints указаны примеры запросов, ответы, коды ошибок и пояснения к полям. Перед ручной проверкой нажмите `Authorize` и передайте JWT access token в формате `Bearer <access>`.

# 5. Данные и команды ----

## 5.1. Загрузка демонстрационных прайсов ----

```bash
make data_to_bd
```

Команда читает `data/shop1.yaml` и `data/shop2.yaml`. Повторный запуск обновляет существующие товары, предложения и параметры без создания дублей. Предустановленные ownerless-магазины, категории, товары и предложения приводятся к активным статусам, чтобы demo-каталог был виден через `/api/products/`.

Для точечной загрузки доступны отдельные цели:

```bash
make data_to_bd_shop1
make data_to_bd_shop2
```

Во втором прайсе есть товары, которые уже присутствуют у первого магазина. Это проверяет сценарий, где один каталоговый товар имеет несколько предложений `ProductInfo` от разных магазинов.

При фильтрации каталога условия `shop_id`, `price_min`, `price_max` и `parameter` применяются к одному и тому же предложению `ProductInfo`, поэтому API не смешивает цену одного магазина с характеристикой или магазином другого.

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

- Массовая загрузка YAML-прайсов выполняется management command; через API магазин управляет уже созданными предложениями.
- Email backend по умолчанию выводит письма в консоль.
