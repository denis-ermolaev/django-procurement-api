# 1. API сервиса закупок ----

Все бизнес-endpoint'ы требуют JWT:

```http
Authorization: Bearer <access-token>
```

Swagger доступен по `/api/docs/`, OpenAPI schema - по `/api/schema/`.

## 1.1. Роли ----

- `buyer` - покупатель: каталог, предложения, корзина, контакты, заказы.
- `shop` - поставщик: профиль магазина, предложения, импорт, свои позиции
  заказов.
- `admin` - администратор: пользователи, магазины, справочники, предложения,
  заказы.

## 1.2. Каталог и предложения ----

- `GET /api/products/` - общий каталог `Product`.
- `GET /api/products/{id}/` - legacy карточка `ProductInfo` по ID предложения.
- `GET /api/products/{id}/offers/` - предложения выбранного товара.
- `GET /api/offers/` - список доступных предложений с фильтрами.
- `GET /api/offers/{id}/` - карточка доступного предложения.

`Product` - общий товар без цены и остатка. `ProductInfo` в API считается
`Offer`: конкретный магазин, цена, остаток, модель, статус и характеристики.

## 1.3. Корзина ----

- `GET /api/basket/` - объект текущей корзины `{id, state, items, total}`.
- `DELETE /api/basket/` - очистить текущую корзину.
- `POST /api/basket/items/` - добавить offer в корзину.
- `PATCH /api/basket/items/{id}/` - изменить quantity позиции.
- `DELETE /api/basket/items/{id}/` - удалить позицию.

Legacy на переходный период:

- `POST /api/basket/` - добавление позиции.
- `DELETE /api/basket/?item_id=...` - удаление позиции по query-параметру.
- `product_info_id` принимается как alias для `offer_id`.

## 1.4. Контакты ----

- `GET /api/contacts/` - список контактов текущего покупателя.
- `POST /api/contacts/` - создать контакт.
- `GET /api/contacts/{id}/` - получить свой контакт.
- `PATCH /api/contacts/{id}/` - обновить свой контакт.
- `DELETE /api/contacts/{id}/` - удалить или soft-delete контакт.

Legacy на переходный период:

- `GET /api/contact/`
- `POST /api/contact/`
- `DELETE /api/contact/?id=...`

## 1.5. Заказы ----

- `POST /api/order/confirm/` - подтвердить корзину, зарезервировать остатки и
  записать ценовые снимки.
- `GET /api/orders/` - история заказов без корзин.
- `GET /api/orders/{id}/` - детали заказа.
- `PATCH /api/orders/{id}/` - legacy отмена покупателем через
  `{"state": "canceled"}` до начала обработки.

История и детали заказа считают суммы по snapshot-полям `OrderItem`, поэтому
изменение текущей цены offer не меняет оформленный заказ.

## 1.6. Магазин ----

- `POST /api/shops/register/` - заявка магазина и пользователь `shop`.
- `GET /api/shop/profile/` - профиль своего магазина.
- `PATCH /api/shop/profile/` - обновить профиль и `is_accepting_orders`.
- `GET /api/shop/offers/` - свои предложения.
- `POST /api/shop/offers/` - создать предложение.
- `PATCH /api/shop/offers/{id}/` - обновить свое предложение.
- `POST /api/shop/imports/` - синхронный YAML-импорт прайса.
- `GET /api/shop/order-items/` - свои позиции заказов.
- `PATCH /api/shop/order-items/{id}/` - перевести свою позицию по автомату.

Магазин должен быть `status=active`; для новых заказов и обработки позиций также
важен `is_accepting_orders=True`.

## 1.7. Администрирование ----

- `GET/PATCH /api/admin/users/{id}/`
- `GET/PATCH /api/admin/shops/{id}/`
- `POST /api/admin/shops/{id}/approve/`
- `POST /api/admin/shops/{id}/block/`
- `GET/POST/PATCH /api/admin/categories/`
- `GET/POST/PATCH /api/admin/products/`
- `GET/POST/PATCH /api/admin/parameters/`
- `GET/PATCH /api/admin/offers/{id}/`
- `GET/PATCH /api/admin/orders/{id}/`
- `PATCH /api/admin/order-items/{id}/`

Административная отмена заказа требует причину. Отправленные и доставленные
позиции не откатываются к досылочным статусам без отдельной возвратной операции.
