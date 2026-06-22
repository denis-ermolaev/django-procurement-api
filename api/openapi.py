from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)

from api.serializers import (
    AddToBasketSerializer,
    BasketItemResponseSerializer,
    ContactListResponseSerializer,
    ContactResponseSerializer,
    ContactSerializer,
    ErrorDetailSerializer,
    OrderConfirmResponseSerializer,
    OrderConfirmSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    OrderUpdateSerializer,
    PaginatedOrderHistoryResponseSerializer,
    PaginatedProductResponseSerializer,
    ProductInfoSerializer,
)

# 1. Общие ответы OpenAPI ----
AUTH_REQUIRED_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description="JWT access token не передан, просрочен или некорректен.",
    examples=[
        OpenApiExample(
            "Нет JWT",
            value={"detail": "Authentication credentials were not provided."},
            response_only=True,
        )
    ],
)
NOT_FOUND_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description="Запрошенный объект не найден или не принадлежит текущему пользователю.",
    examples=[
        OpenApiExample(
            "Объект не найден",
            value={"detail": "Not found."},
            response_only=True,
        )
    ],
)
VALIDATION_ERROR_RESPONSE = OpenApiResponse(
    response=OpenApiTypes.OBJECT,
    description="Ошибка валидации. Ответ содержит поля запроса и список ошибок по каждому полю.",
    examples=[
        OpenApiExample(
            "Ошибка поля",
            value={"field": ["This field is required."]},
            response_only=True,
        )
    ],
)


# 2. Схемы endpoints ----
product_list_schema = extend_schema(
    operation_id="product_list",
    summary="Список товаров",
    description=(
        "Возвращает постраничный каталог сущностей Product. Product - это общий "
        "товар в каталоге, а ProductInfo - конкретное предложение магазина с "
        "ценой, остатком и характеристиками. Поэтому фильтры по цене, магазину "
        "и характеристикам применяются через связанные ProductInfo, но в ответе "
        "остаются сами товары Product."
    ),
    tags=["Products"],
    parameters=[
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Номер страницы. Нумерация начинается с 1.",
        ),
        OpenApiParameter(
            name="page_size",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Количество товаров на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по названию товара (регистронезависимый)",
            examples=[
                OpenApiExample(
                    "Поиск смартфона",
                    value="Xiaomi",
                )
            ],
        ),
        OpenApiParameter(
            name="category_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="ID категории",
        ),
        OpenApiParameter(
            name="shop_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="ID магазина, у которого есть предложение ProductInfo для товара",
        ),
        OpenApiParameter(
            name="price_min",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Минимальная цена товара (в любом магазине)",
        ),
        OpenApiParameter(
            name="price_max",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Максимальная цена товара (в любом магазине)",
        ),
        OpenApiParameter(
            name="parameter",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                "Фильтр по характеристике предложения в формате "
                "'имя_параметра:значение'. Значение ищется без учета регистра."
            ),
            examples=[
                OpenApiExample(
                    "Фильтр по характеристике",
                    value="color:black",
                )
            ],
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PaginatedProductResponseSerializer,
            description="Постраничный список товаров.",
            examples=[
                OpenApiExample(
                    "Каталог после загрузки demo YAML",
                    value={
                        "count": 18,
                        "next": "http://testserver/api/products/?page=2&page_size=2",
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "category": 1,
                                "name": "Смартфон Apple iPhone XS Max 512GB (золотистый)",
                            },
                            {
                                "id": 2,
                                "category": 1,
                                "name": "Смартфон Apple iPhone XR 256GB (красный)",
                            },
                        ],
                    },
                    response_only=True,
                )
            ],
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
    },
)

product_detail_schema = extend_schema(
    operation_id="product_offer_retrieve",
    summary="Детальная информация о предложении",
    description=(
        "Возвращает конкретное предложение ProductInfo. Это не общий товар Product, "
        "а предложение конкретного магазина: ссылка на товар и магазин, название "
        "из прайса, остаток, фактическая цена и рекомендованная цена."
    ),
    tags=["Products"],
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="ID предложения ProductInfo.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=ProductInfoSerializer,
            description="Данные предложения товара.",
            examples=[
                OpenApiExample(
                    "Предложение товара",
                    value={
                        "id": 1,
                        "name": "Смартфон Apple iPhone XS Max 512GB (золотистый)",
                        "quantity": 14,
                        "price": 110000,
                        "price_rrc": 116990,
                        "product": 1,
                        "shop": 1,
                    },
                    response_only=True,
                )
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
        404: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="Предложение с указанным id не найдено.",
        ),
    },
)

basket_retrieve_schema = extend_schema(
    operation_id="basket_retrieve",
    summary="Получить корзину",
    description=(
        "Возвращает позиции текущей корзины пользователя. Текущая корзина - первый "
        "заказ пользователя в статусе basket. Если корзины нет или она пуста, "
        "возвращается пустой массив. Оформленные заказы в ответ не попадают."
    ),
    tags=["Basket"],
    responses={
        200: OpenApiResponse(
            response=OrderItemSerializer(many=True),
            description="Позиции текущей корзины.",
            examples=[
                OpenApiExample(
                    "Корзина с одной позицией",
                    value=[
                        {
                            "id": 1,
                            "quantity": 2,
                            "order": 1,
                            "product_info": 1,
                        }
                    ],
                    response_only=True,
                ),
                OpenApiExample(
                    "Пустая корзина",
                    value=[],
                    response_only=True,
                ),
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
    },
)

basket_add_schema = extend_schema(
    operation_id="basket_add_item",
    summary="Добавить товар в корзину",
    description=(
        "Добавляет предложение ProductInfo в корзину текущего пользователя. "
        "Если открытой корзины нет, она создается автоматически. Если такая "
        "позиция уже есть в корзине, quantity увеличивается на переданное значение. "
        "Итоговое количество не может превышать остаток ProductInfo.quantity."
    ),
    tags=["Basket"],
    request=AddToBasketSerializer,
    examples=[
        OpenApiExample(
            "Добавить предложение",
            value={"product_info_id": 1, "quantity": 2},
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=BasketItemResponseSerializer,
            description="Созданная или обновленная позиция корзины.",
            examples=[
                OpenApiExample(
                    "Позиция корзины",
                    value={
                        "data": {
                            "id": 1,
                            "quantity": 2,
                            "order": 1,
                            "product_info": 1,
                        }
                    },
                    response_only=True,
                )
            ],
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        404: OpenApiResponse(
            response=ErrorDetailSerializer,
            description="Предложение товара product_info_id не найдено.",
        ),
    },
)

basket_delete_schema = extend_schema(
    operation_id="basket_delete_item",
    summary="Удалить позицию из корзины",
    description=(
        "Удаляет позицию OrderItem из корзины текущего пользователя. "
        "Основной параметр для удаления: item_id. order_id можно передать "
        "дополнительно для строгой проверки корзины. Старое имя product_info_id "
        "временно поддерживается как алиас item_id для обратной совместимости."
    ),
    tags=["Basket"],
    parameters=[
        OpenApiParameter(
            name="item_id",
            type=OpenApiTypes.INT,
            required=True,
            location=OpenApiParameter.QUERY,
            description="ID позиции корзины OrderItem, которую нужно удалить.",
        ),
        OpenApiParameter(
            name="product_info_id",
            type=OpenApiTypes.INT,
            required=False,
            location=OpenApiParameter.QUERY,
            description="Устаревший алиас item_id.",
        ),
        OpenApiParameter(
            name="order_id",
            type=OpenApiTypes.INT,
            required=False,
            location=OpenApiParameter.QUERY,
            description="Опциональный ID заказа-корзины для дополнительной проверки.",
        ),
    ],
    responses={
        204: OpenApiResponse(description="Позиция удалена, тело ответа пустое."),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

contact_list_schema = extend_schema(
    operation_id="contact_list",
    summary="Список адресов доставки",
    description=(
        "Возвращает адреса доставки текущего пользователя в обертке data. "
        "Если адресов еще нет, возвращается пустой список."
    ),
    tags=["Contacts"],
    responses={
        200: OpenApiResponse(
            response=ContactListResponseSerializer,
            description="Список адресов доставки текущего пользователя.",
            examples=[
                OpenApiExample(
                    "Адреса доставки",
                    value={
                        "data": [
                            {
                                "id": 1,
                                "city": "Kaliningrad",
                                "street": "Lenina",
                                "house": "1",
                                "structure": "",
                                "building": "",
                                "apartment": "10",
                                "phone": "+70000000000",
                            }
                        ]
                    },
                    response_only=True,
                )
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
    },
)

contact_create_schema = extend_schema(
    operation_id="contact_create",
    summary="Создать адрес доставки",
    description=(
        "Создает адрес доставки для текущего пользователя. Поля city, street и phone "
        "обязательны; house, structure, building и apartment могут быть пустыми строками."
    ),
    tags=["Contacts"],
    request=ContactSerializer,
    examples=[
        OpenApiExample(
            "Адрес доставки",
            value={
                "city": "Kaliningrad",
                "street": "Lenina",
                "house": "1",
                "structure": "",
                "building": "",
                "apartment": "10",
                "phone": "+70000000000",
            },
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=ContactResponseSerializer,
            description="Созданный адрес доставки в обертке data.",
            examples=[
                OpenApiExample(
                    "Созданный адрес",
                    value={
                        "data": {
                            "id": 1,
                            "city": "Kaliningrad",
                            "street": "Lenina",
                            "house": "1",
                            "structure": "",
                            "building": "",
                            "apartment": "10",
                            "phone": "+70000000000",
                        }
                    },
                    response_only=True,
                )
            ],
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
    },
)

contact_delete_schema = extend_schema(
    operation_id="contact_delete",
    summary="Удалить адрес доставки",
    description="Удаляет адрес доставки текущего пользователя по query-параметру id.",
    tags=["Contacts"],
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            required=True,
            location=OpenApiParameter.QUERY,
            description="ID адреса доставки.",
        ),
    ],
    responses={
        204: OpenApiResponse(description="Адрес удален, тело ответа пустое."),
        401: AUTH_REQUIRED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

order_confirm_schema = extend_schema(
    operation_id="order_confirm",
    summary="Подтвердить заказ",
    description=(
        "Переводит заказ текущего пользователя из статуса basket в confirmed, "
        "привязывает выбранный адрес доставки и отправляет e-mail уведомления. "
        "И заказ, и адрес должны принадлежать текущему пользователю; заказ должен "
        "содержать хотя бы одну позицию."
    ),
    tags=["Orders"],
    request=OrderConfirmSerializer,
    examples=[
        OpenApiExample(
            "Подтвердить корзину",
            value={"order_id": 1, "contact_id": 1},
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=OrderConfirmResponseSerializer,
            description="Заказ подтвержден.",
            examples=[
                OpenApiExample(
                    "Заказ подтвержден",
                    value={"status": "Order confirmed"},
                    response_only=True,
                )
            ],
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        404: OpenApiResponse(
            response=ErrorDetailSerializer,
            description=(
                "Заказ не найден, не принадлежит текущему пользователю, уже не в "
                "статусе basket, либо contact_id не найден у текущего пользователя."
            ),
        ),
    },
)

order_history_schema = extend_schema(
    operation_id="order_history_list",
    summary="История заказов",
    description=(
        "Возвращает постраничную историю заказов текущего пользователя. "
        "Заказы в статусе basket не включаются. total_sum рассчитывается как "
        "сумма quantity * price по позициям заказа. Содержимое конкретного заказа "
        "доступно через GET /api/orders/{id}/."
    ),
    tags=["Orders"],
    parameters=[
        OpenApiParameter(
            name="page",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Номер страницы. Нумерация начинается с 1.",
        ),
        OpenApiParameter(
            name="page_size",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Количество заказов на страницу. Максимум: 100.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PaginatedOrderHistoryResponseSerializer,
            description="Постраничный список заказов без корзин.",
            examples=[
                OpenApiExample(
                    "История заказов",
                    value={
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 4,
                                "dt": "2026-06-21T16:40:31.083167Z",
                                "total_sum": 220000,
                                "state": "confirmed",
                            }
                        ],
                    },
                    response_only=True,
                ),
                OpenApiExample(
                    "Пустая история",
                    value={
                        "count": 0,
                        "next": None,
                        "previous": None,
                        "results": [],
                    },
                    response_only=True,
                ),
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
    },
)

order_retrieve_schema = extend_schema(
    operation_id="order_retrieve",
    summary="Детальная информация о заказе",
    description=(
        "Возвращает заказ по id, если он принадлежит текущему пользователю. "
        "Ответ включает адрес доставки, итоговую сумму и позиции заказа."
    ),
    tags=["Orders"],
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="ID заказа текущего пользователя.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=OrderDetailSerializer,
            description="Данные заказа и его позиции.",
            examples=[
                OpenApiExample(
                    "Заказ",
                    value={
                        "id": 1,
                        "user": 2,
                        "dt": "2026-06-21T16:40:31.083167Z",
                        "state": "confirmed",
                        "contact": 3,
                        "total_sum": 220000,
                        "items": [
                            {
                                "id": 10,
                                "quantity": 2,
                                "order": 1,
                                "product_info": 1,
                            }
                        ],
                    },
                    response_only=True,
                )
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

order_update_schema = extend_schema(
    operation_id="order_update",
    summary="Обновить заказ",
    description=(
        "Частично обновляет статус заказа текущего пользователя. Разрешены "
        "бизнес-статусы new, confirmed, assembled, sent, delivered и canceled. "
        "Статус basket через этот endpoint не выставляется."
    ),
    tags=["Orders"],
    request=OrderUpdateSerializer,
    parameters=[
        OpenApiParameter(
            name="id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="ID заказа текущего пользователя.",
        ),
    ],
    examples=[
        OpenApiExample(
            "Перевести в доставлен",
            value={"state": "delivered"},
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=OrderDetailSerializer,
            description="Обновленный заказ.",
            examples=[
                OpenApiExample(
                    "Заказ после PATCH",
                    value={
                        "id": 1,
                        "user": 2,
                        "dt": "2026-06-21T16:40:31.083167Z",
                        "state": "delivered",
                        "contact": 3,
                        "total_sum": 220000,
                        "items": [
                            {
                                "id": 10,
                                "quantity": 2,
                                "order": 1,
                                "product_info": 1,
                            }
                        ],
                    },
                    response_only=True,
                )
            ],
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
