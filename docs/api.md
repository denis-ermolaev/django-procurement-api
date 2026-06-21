# 1. API guide ----

Практическая памятка по публичному API. Примеры ниже проверены через DRF `APIClient` на чистой тестовой базе с загруженными файлами `data/shop1.yaml` и `data/shop2.yaml`.

ID в примерах соответствуют чистой базе после последовательной загрузки двух demo-прайсов. В уже заполненной базе ID могут отличаться, но структура ответов сохраняется. Значения `dt` приведены как пример ISO-8601 timestamp; фактическое время будет равно моменту создания заказа.

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

# 3. Каталог ----

## 3.1. Список товаров ----

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
      "name": "Смартфон Apple iPhone XS Max 512GB (золотистый)"
    },
    {
      "id": 2,
      "category": 1,
      "name": "Смартфон Apple iPhone XR 256GB (красный)"
    }
  ]
}
```

Важно: список возвращает сущности `Product`, а фильтры по цене, магазину и характеристикам применяются через связанные предложения `ProductInfo`.

## 3.2. Фильтры каталога ----

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

## 3.3. Детальная информация о предложении ----

```http
GET /api/products/1/
Authorization: Bearer <access-token>
```

Несмотря на путь `/api/products/{id}/`, endpoint принимает ID предложения `ProductInfo`, а не ID товара `Product`.

Ответ `200 OK`:

```json
{
  "id": 1,
  "name": "Смартфон Apple iPhone XS Max 512GB (золотистый)",
  "quantity": 14,
  "price": 110000,
  "price_rrc": 116990,
  "product": 1,
  "shop": 1
}
```

# 4. Корзина ----

## 4.1. Пустая корзина ----

```http
GET /api/basket/
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
[]
```

## 4.2. Добавление позиции ----

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

Если запрошенное количество превышает остаток `ProductInfo.quantity`, API возвращает `400 Bad Request`:

```json
{
  "quantity": "Запрошенное количество превышает доступный остаток. Доступно: 14, уже в корзине: 2."
}
```

## 4.3. Просмотр корзины с позициями ----

```http
GET /api/basket/
Authorization: Bearer <access-token>
```

Ответ `200 OK`:

```json
[
  [
    {
      "id": 1,
      "quantity": 2,
      "order": 1,
      "product_info": 1
    }
  ]
]
```

Формат ответа - массив заказов-корзин, где каждый заказ представлен массивом позиций. В текущем бизнес-сценарии обычно есть одна открытая корзина.

## 4.4. Удаление позиции ----

```http
DELETE /api/basket/?order_id=1&item_id=1
Authorization: Bearer <access-token>
```

Успешный ответ `204 No Content` приходит без тела.

Параметр `product_info_id` временно поддерживается как устаревший alias для `item_id`. Для новых клиентов используйте `item_id`, потому что удаляется именно позиция `OrderItem`, а не предложение `ProductInfo`.

Если не передать `item_id`, API возвращает `400 Bad Request`:

```json
{
  "item_id": [
    "Передайте item_id позиции корзины."
  ]
}
```

# 5. Адреса доставки ----

## 5.1. Создание адреса ----

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

## 5.2. Список адресов ----

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

## 5.3. Удаление адреса ----

```http
DELETE /api/contact/?id=1
Authorization: Bearer <access-token>
```

Успешный ответ `204 No Content` приходит без тела. Удалить можно только свой адрес.

# 6. Заказы ----

## 6.1. Подтверждение корзины ----

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

Подтвердить можно только свою непустую корзину в статусе `basket`. После подтверждения заказ получает статус `confirmed`, к нему привязывается адрес доставки, а сервис отправляет письмо клиенту и администраторам.

## 6.2. История заказов ----

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

## 6.3. Детальная информация о заказе ----

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
  "state": "confirmed"
}
```

Endpoint возвращает заказ только владельцу. Чужой или несуществующий заказ возвращает `404 Not Found`.

## 6.4. Частичное обновление заказа ----

```http
PATCH /api/orders/1/
Authorization: Bearer <access-token>
Content-Type: application/json
```

```json
{
  "state": "new"
}
```

Ответ `200 OK`:

```json
{
  "id": 1,
  "user": 2,
  "dt": "2026-06-21T16:40:31.083167Z",
  "state": "new"
}
```

Текущая версия serializer-а разрешает только значение `state=new`. Например, `state=delivered` вернет `400 Bad Request`:

```json
{
  "state": [
    "\"delivered\" is not a valid choice."
  ]
}
```

# 7. Swagger UI ----

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
