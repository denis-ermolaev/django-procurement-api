# 1. API guide ----

Практическая памятка по публичному API. Примеры ниже проверены через DRF `APIClient` на чистой тестовой базе с загруженными файлами `data/shop1.yaml` и `data/shop2.yaml`.

ID в примерах соответствуют чистой базе после последовательной загрузки двух demo-прайсов. В уже заполненной базе ID могут отличаться, но структура ответов сохраняется. Значения `dt` приведены как пример ISO-8601 timestamp; фактическое время будет равно моменту создания заказа.

Повторная загрузка `data/shop1.yaml` и `data/shop2.yaml` через `make data_to_bd` обновляет demo-каталог и приводит предустановленные ownerless-магазины, категории, товары и предложения к активным статусам, чтобы они были видны через публичный каталог `/api/products/`.

# 2. Аутентификация ----

## 2.1. Регистрация ----

Запрос:

```http
POST /api/auth/users/
Content-Type: application/json
```

```json
{
  "first_name": "Ivan",
  "last_name": "Buyer",
  "email": "ivan@example.com",
  "password": "strong-test-password"
}
```

Ответ `201 Created`:

```json
{
  "first_name": "Ivan",
  "last_name": "Buyer",
  "email": "ivan@example.com",
  "type": "buyer"
}
```

Пароль в ответе не возвращается. Новый пользователь создается неактивным, потому что Djoser отправляет письмо активации. В локальном Docker-запуске письмо видно в логах контейнера:

```bash
docker compose logs -f web
```

Обычная регистрация всегда создает покупателя `type=buyer`. Роли `shop` и `admin` через `/api/auth/users/` создать нельзя: для магазина используется отдельная заявка, администратор создается через административный контур.

## 2.2. Получение JWT ----

Активированный пользователь получает пару токенов:

```http
POST /api/auth/jwt/create/
Content-Type: application/json
```

```json
{
  "email": "buyer@example.com",
  "password": "strong-test-password"
}
```

Ответ `200 OK`:

```json
{
  "refresh": "<refresh-token>",
  "access": "<access-token>"
}
```

Для защищенных endpoints передавайте access token:

```http
Authorization: Bearer <access-token>
```

Если токен не передан, бизнес-эндпоинты возвращают `401 Unauthorized`:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

## 2.3. Общие соглашения ----

- Все бизнес-эндпоинты работают только с данными текущего JWT-пользователя.
- Ошибки прав доступа к чужим объектам возвращаются как `404 Not Found`, чтобы не раскрывать существование чужих заказов, адресов и позиций.
- Ошибки валидации возвращаются как объект, где ключ - имя поля, а значение - список сообщений или строка ошибки.
- В примерах ниже `id` у позиции корзины или заказа - это ID `OrderItem`. Его нужно использовать для удаления позиции.

# 3. Магазины ----

## 3.1. Регистрация магазина ----

```http
POST /api/shops/register/
Content-Type: application/json
```

```json
{
  "first_name": "Shop",
  "last_name": "Owner",
  "email": "supplier@example.com",
  "password": "strong-test-password",
  "shop_name": "Supplier shop",
  "url": "https://supplier.example.com"
}
```

Ответ `201 Created`:

```json
{
  "user": {
    "id": 10,
    "email": "supplier@example.com",
    "first_name": "Shop",
    "last_name": "Owner",
    "type": "shop",
    "is_active": false
  },
  "shop": {
    "id": 4,
    "name": "Supplier shop",
    "url": "https://supplier.example.com",
    "owner": 10,
    "status": "pending",
    "created_at": "2026-06-22T10:00:00Z",
    "updated_at": "2026-06-22T10:00:00Z"
  }
}
```

После регистрации создается неактивный пользователь `type=shop` и связанный магазин в статусе `pending`. Магазин сможет продавать только после одобрения администратором.

## 3.2. Одобрение и блокировка магазина ----

Административные endpoints доступны только пользователям с `is_staff=true` и `type=admin`.

```http
POST /api/admin/shops/4/approve/
Authorization: Bearer <admin-access-token>
```

Ответ `200 OK` содержит магазин со статусом `active`.

```http
POST /api/admin/shops/4/block/
Authorization: Bearer <admin-access-token>
```

Ответ `200 OK` содержит магазин со статусом `blocked`.

## 3.3. Профиль и предложения магазина ----

Пользователь с ролью `shop` работает только со своим магазином:

- `GET /api/shop/profile/` - профиль своего магазина.
- `PATCH /api/shop/profile/` - обновление `name` и `url`.
- `GET /api/shop/offers/` - список своих предложений.
- `POST /api/shop/offers/` - создание предложения для существующего активного `Product`.
- `PATCH /api/shop/offers/{id}/` - обновление своего предложения.

Создавать и изменять предложения может только активный магазин `status=active`. Магазин не может передать или изменить `shop`: предложение всегда привязывается к магазину текущего JWT-пользователя.

Для предложений действуют общие числовые ограничения: `quantity >= 0`, `reserved_quantity >= 0`, `reserved_quantity <= quantity`, `price > 0`, `price_rrc >= 0`. Эти правила проверяются serializer'ами API и дополнительно закреплены DB constraints.

Статусы предложения:

- `active` - видно покупателям, если магазин, товар и категория тоже активны.
- `hidden` - скрыто магазином.
- `archived` - архивировано магазином.
- `blocked` - заблокировано администратором.

## 3.4. Позиции заказов магазина ----

Магазин работает не со всем заказом, а только со своими позициями:

- `GET /api/shop/order-items/` - позиции заказов, относящиеся к предложениям магазина.
- `PATCH /api/shop/order-items/{id}/` - перевод позиции на следующий статус.

Разрешенная цепочка магазина: `confirmed -> accepted -> assembled -> sent -> delivered`. Отмена разрешена до отправки. При переходе в `sent` зарезервированный остаток списывается из физического остатка.

# 4. Каталог ----

## 4.1. Список товаров ----

```http
GET /api/products/?page_size=2
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
{
  "count": 18,
  "next": "http://testserver/api/products/?page=2&page_size=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "category": 1,
      "name": "Смартфон Apple iPhone XS Max 512GB (золотистый)",
      "status": "active"
    },
    {
      "id": 2,
      "category": 1,
      "name": "Смартфон Apple iPhone XR 256GB (красный)",
      "status": "active"
    }
  ]
}
```

Важно: список возвращает сущности `Product`. Это общий товар каталога без цены и остатка. Цена, остаток, магазин и характеристики находятся в `ProductInfo`, поэтому фильтры по цене, магазину и характеристикам применяются через связанные предложения. Если передано несколько фильтров предложения одновременно, они должны совпасть на одном и том же `ProductInfo`; это важно для товаров, которые продаются в нескольких магазинах.

## 4.2. Фильтры каталога ----

Поддерживаются query-параметры:

- `search` - поиск по названию товара, без учета регистра.
- `category_id` - ID категории из базы.
- `shop_id` - ID магазина, где есть предложение товара.
- `price_min` и `price_max` - границы цены по предложениям.
- `parameter` - характеристика в формате `имя:значение`.
- `page` и `page_size` - пагинация, максимум `page_size=100`.

Пример:

```http
GET /api/products/?search=Xiaomi&page_size=10
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 9,
      "category": 1,
      "name": "Smartphone Xiaomi Mi 10T Pro 256GB (cosmic black)"
    }
  ]
}
```

Если `parameter` передан без двоеточия, API возвращает `400 Bad Request`:

```json
{
  "parameter": [
    "Ожидаемый формат: имя_параметра:значение."
  ]
}
```

## 4.3. Детальная информация о предложении ----

```http
GET /api/products/1/
Authorization: Bearer <access-token>
```

Несмотря на путь `/api/products/{id}/`, endpoint принимает ID предложения `ProductInfo`, а не ID товара `Product`.

Используйте этот endpoint, когда нужно показать карточку конкретного предложения магазина: цену, остаток и связь с магазином. Если один и тот же товар продают несколько магазинов, у него будет несколько записей `ProductInfo`.

Ответ `200 OK`:

```json
{
  "id": 1,
  "name": "Смартфон Apple iPhone XS Max 512GB (золотистый)",
  "quantity": 14,
  "available_quantity": 14,
  "price": 110000,
  "price_rrc": 116990,
  "product": 1,
  "shop": 1
}
```

# 5. Корзина ----

Корзина хранится как заказ в статусе `basket`. Клиенту не нужно заранее создавать заказ или передавать `order_id` при добавлении товара: API сам найдет текущую корзину пользователя или создаст новую. Текущая корзина определяется как первый открытый `basket`-заказ пользователя.

## 5.1. Пустая корзина ----

```http
GET /api/basket/
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
[]
```

## 5.2. Добавление позиции ----

```http
POST /api/basket/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "product_info_id": 1,
  "quantity": 2
}
```

Ответ `200 OK`:

```json
{
  "data": {
    "id": 1,
    "quantity": 2,
    "order": 1,
    "product_info": 1
  }
}
```

Если открытой корзины нет, API создает заказ со статусом `basket`. Если такая позиция уже есть, количество увеличивается.

В одном заказе могут быть предложения от разных поставщиков. Ограничение проверяется только по остатку конкретного `ProductInfo`: итоговое количество позиции в корзине не может быть больше доступного остатка.

Если запрошенное количество превышает доступный остаток `ProductInfo.quantity - ProductInfo.reserved_quantity`, API возвращает `400 Bad Request`:

```json
{
  "quantity": "Запрошенное количество превышает доступный остаток. Доступно: 14, уже в корзине: 2."
}
```

## 5.3. Просмотр корзины с позициями ----

```http
GET /api/basket/
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
[
  {
    "id": 1,
    "quantity": 2,
    "order": 1,
    "product_info": 1
  }
]
```

Формат ответа - массив позиций текущей корзины. Текущая корзина определяется как первый заказ пользователя в статусе `basket`; новые позиции также добавляются именно в нее.

## 5.4. Удаление позиции ----

```http
DELETE /api/basket/?item_id=1
Authorization: Bearer <access-token>
```

Успешный ответ `204 No Content` приходит без тела.

Для новых клиентов используйте `item_id`, потому что удаляется именно позиция `OrderItem`, а не предложение `ProductInfo`. Опционально можно передать `order_id` для дополнительной проверки, что позиция находится в конкретной корзине. Параметр `product_info_id` временно поддерживается как устаревший alias для `item_id`.

Если не передать идентификатор позиции, API возвращает `400 Bad Request`:

```json
{
  "item_id": [
    "Передайте item_id позиции корзины."
  ]
}
```

# 6. Адреса доставки ----

## 6.1. Создание адреса ----

```http
POST /api/contact/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "city": "Kaliningrad",
  "street": "Lenina",
  "house": "1",
  "structure": "",
  "building": "",
  "apartment": "10",
  "phone": "+70000000000"
}
```

Ответ `200 OK`:

```json
{
  "data": {
    "id": 1,
    "city": "Kaliningrad",
    "street": "Lenina",
    "house": "1",
    "structure": "",
    "building": "",
    "apartment": "10",
    "phone": "+70000000000"
  }
}
```

Обязательные поля: `city`, `street`, `phone`. Остальные поля можно передать пустыми строками.

Если обязательные поля отсутствуют:

```json
{
  "street": [
    "This field is required."
  ],
  "phone": [
    "This field is required."
  ]
}
```

## 6.2. Список адресов ----

```http
GET /api/contact/
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
{
  "data": [
    {
      "id": 1,
      "city": "Kaliningrad",
      "street": "Lenina",
      "house": "1",
      "structure": "",
      "building": "",
      "apartment": "10",
      "phone": "+70000000000"
    }
  ]
}
```

Если адресов нет:

```json
{
  "data": []
}
```

## 6.3. Удаление адреса ----

```http
DELETE /api/contact/?id=1
Authorization: Bearer <access-token>
```

Успешный ответ `204 No Content` приходит без тела. Удалить можно только свой адрес.

# 7. Заказы ----

## 7.1. Статусы заказа ----

Поддерживаемые статусы:

- `basket` - текущая корзина; не входит в историю заказов.
- `confirmed` - заказ подтвержден клиентом.
- `processing` - хотя бы одна позиция принята или собирается магазином.
- `sent` - все неотмененные позиции отправлены.
- `delivered` - все неотмененные позиции доставлены.
- `partially_canceled` - часть позиций отменена.
- `canceled` - заказ отменен.

Покупатель через `PATCH /api/orders/{id}/` может только отменить свой заказ до начала обработки. Магазин меняет статусы своих `OrderItem`, после чего статус заказа пересчитывается. Администратор может менять административные статусы через `/api/admin/orders/{id}/`.

## 7.2. Подтверждение корзины ----

```http
POST /api/order/confirm/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "order_id": 1,
  "contact_id": 1
}
```

Ответ `200 OK`:

```json
{
  "status": "Order confirmed"
}
```

Подтвердить можно только свою непустую корзину в статусе `basket`. После подтверждения заказ получает статус `confirmed`, все позиции получают статус `confirmed`, остаток предложений резервируется, к заказу привязывается адрес доставки, а сервис отправляет письмо клиенту и администраторам.

Для отправки писем используются `DJANGO_DEFAULT_FROM_EMAIL`, `DJANGO_EMAIL_BACKEND` и `DJANGO_ADMIN_EMAILS`. В локальном окружении по умолчанию письма выводятся в консоль.

## 7.3. История заказов ----

```http
GET /api/orders/
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "dt": "2026-06-21T16:40:31.083167Z",
      "total_sum": 220000,
      "state": "confirmed"
    }
  ]
}
```

В историю не попадают заказы со статусом `basket`. Поле `total_sum` считается как сумма `quantity * price` по всем позициям заказа.

## 7.4. Детальная информация о заказе ----

```http
GET /api/orders/1/
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
{
  "id": 1,
  "user": 2,
  "dt": "2026-06-21T16:40:31.083167Z",
  "state": "confirmed",
  "contact": 1,
  "total_sum": 220000,
  "items": [
    {
      "id": 1,
      "quantity": 2,
      "state": "confirmed",
      "order": 1,
      "product_info": 1
    }
  ]
}
```

Endpoint возвращает заказ только владельцу, включая позиции заказа и итоговую сумму. Чужой или несуществующий заказ возвращает `404 Not Found`.

## 7.5. Отмена заказа покупателем ----

```http
PATCH /api/orders/1/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "state": "canceled"
}
```

Ответ `200 OK`:

```json
{
  "id": 1,
  "user": 2,
  "dt": "2026-06-21T16:40:31.083167Z",
  "state": "canceled",
  "contact": 1,
  "cancellation_reason": "",
  "total_sum": 220000,
  "items": [
    {
      "id": 1,
      "quantity": 2,
      "state": "canceled",
      "order": 1,
      "product_info": 1
    }
  ]
}
```

Если заказ уже в обработке магазином, покупательская отмена вернет `400 Bad Request`. Например, неизвестный или запрещенный статус вернет:

```json
{
  "state": [
    "\"delivered\" is not a valid choice."
  ]
}
```

# 8. Администрирование ----

Административные endpoints требуют JWT пользователя с `is_staff=true` и `type=admin`.

Основные endpoints:

- `GET /api/admin/users/`, `PATCH /api/admin/users/{id}/` - пользователи, блокировка/разблокировка, смена роли.
- `GET /api/admin/shops/`, `PATCH /api/admin/shops/{id}/` - магазины и их статусы.
- `POST /api/admin/shops/{id}/approve/`, `POST /api/admin/shops/{id}/block/` - быстрые действия модерации магазина.
- `GET|POST /api/admin/categories/`, `PATCH /api/admin/categories/{id}/` - категории.
- `GET|POST /api/admin/products/`, `PATCH /api/admin/products/{id}/` - глобальные товары.
- `GET|POST /api/admin/parameters/`, `PATCH /api/admin/parameters/{id}/` - справочник характеристик.
- `GET /api/admin/offers/`, `PATCH /api/admin/offers/{id}/` - предложения магазинов, включая блокировку некорректных предложений.
- `GET /api/admin/orders/`, `PATCH /api/admin/orders/{id}/` - административная работа с заказами.
- `PATCH /api/admin/order-items/{id}/` - ручная смена статуса позиции заказа.

При административной отмене заказа нужно передать причину:

```json
{
  "state": "canceled",
  "cancellation_reason": "Ошибочный заказ"
}
```

Административная отмена освобождает резерв по неотправленным позициям.

Ограничения административных действий:

- `type=admin` требует `is_staff=true`.
- `type=shop` можно назначить только пользователю со связанным `Shop`.
- Нельзя изменить роль пользователя, который владеет магазином.
- Нельзя сохранить предложение с отрицательным остатком, отрицательной РРЦ, нулевой/отрицательной ценой или резервом больше физического остатка.
- Позицию заказа нельзя вернуть в `basket`.
- Отправленную или доставленную позицию нельзя вернуть к статусам до отправки, потому что складской остаток уже списан.
- Если администратор переводит позицию из досылочного статуса сразу в `sent` или `delivered`, резерв списывается так же, как при отправке магазином.

# 9. Swagger UI ----

Swagger UI доступен по адресу:

```text
http://localhost:8000/api/docs/
```

OpenAPI schema доступна по адресу:

```text
http://localhost:8000/api/schema/
```

В Swagger UI нажмите `Authorize` и передайте токен в формате:

```text
Bearer <access-token>
```

Проверить, что схема собирается без предупреждений:

```bash
make schema_validate_host
```
