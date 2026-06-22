from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)

from api.serializers import (
    AddToBasketSerializer,
    AdminOfferUpdateSerializer,
    AdminOrderItemUpdateSerializer,
    AdminOrderUpdateSerializer,
    AdminShopUpdateSerializer,
    AdminUserUpdateSerializer,
    BasketItemResponseSerializer,
    CategorySerializer,
    ContactListResponseSerializer,
    ContactResponseSerializer,
    ContactSerializer,
    ErrorDetailSerializer,
    OfferSerializer,
    OrderConfirmResponseSerializer,
    OrderConfirmSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    OrderUpdateSerializer,
    PaginatedOrderHistoryResponseSerializer,
    PaginatedProductResponseSerializer,
    ParameterSerializer,
    ProductInfoSerializer,
    ProductSerializer,
    ShopOfferCreateSerializer,
    ShopOfferUpdateSerializer,
    ShopOrderItemUpdateSerializer,
    ShopRegistrationResponseSerializer,
    ShopRegistrationSerializer,
    ShopSerializer,
    UserSerializer,
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
FORBIDDEN_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description="Пользователь авторизован, но его роль не имеет доступа к endpoint.",
    examples=[
        OpenApiExample(
            "Недостаточно прав",
            value={"detail": "Доступ разрешен только администраторам."},
            response_only=True,
        )
    ],
)


# 2. Схемы endpoints ----
shop_register_schema = extend_schema(
    operation_id="shop_register",
    summary="Регистрация магазина",
    description=(
        "Создает пользователя с ролью shop и связанный магазин в статусе pending. "
        "Пользователь создается неактивным: получение JWT доступно только после "
        "активации пользователя, а продажа - после одобрения магазина администратором."
    ),
    tags=["Shops"],
    auth=[],
    request=ShopRegistrationSerializer,
    examples=[
        OpenApiExample(
            "Заявка магазина",
            value={
                "first_name": "Shop",
                "last_name": "Owner",
                "email": "shop@example.com",
                "password": "strong-test-password",
                "shop_name": "Procurement supplier",
                "url": "https://supplier.example.com",
            },
            request_only=True,
        ),
    ],
    responses={
        201: OpenApiResponse(
            response=ShopRegistrationResponseSerializer,
            description="Пользователь магазина и заявка магазина созданы.",
            examples=[
                OpenApiExample(
                    "Созданный магазин",
                    value={
                        "user": {
                            "id": 10,
                            "email": "shop@example.com",
                            "first_name": "Shop",
                            "last_name": "Owner",
                            "type": "shop",
                            "is_active": False,
                        },
                        "shop": {
                            "id": 4,
                            "name": "Procurement supplier",
                            "url": "https://supplier.example.com",
                            "owner": 10,
                            "status": "pending",
                            "created_at": "2026-06-22T10:00:00Z",
                            "updated_at": "2026-06-22T10:00:00Z",
                        },
                    },
                    response_only=True,
                )
            ],
        ),
        400: VALIDATION_ERROR_RESPONSE,
    },
)

admin_shop_approve_schema = extend_schema(
    operation_id="admin_shop_approve",
    summary="Одобрить магазин",
    description=(
        "Администратор переводит магазин в статус active. Endpoint доступен только "
        "пользователям с is_staff=True и type=admin."
    ),
    tags=["Admin"],
    request=None,
    responses={
        200: OpenApiResponse(
            response=ShopSerializer,
            description="Магазин одобрен.",
            examples=[
                OpenApiExample(
                    "Активный магазин",
                    value={
                        "id": 4,
                        "name": "Procurement supplier",
                        "url": "https://supplier.example.com",
                        "owner": 10,
                        "status": "active",
                        "created_at": "2026-06-22T10:00:00Z",
                        "updated_at": "2026-06-22T10:05:00Z",
                    },
                    response_only=True,
                )
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_shop_block_schema = extend_schema(
    operation_id="admin_shop_block",
    summary="Заблокировать магазин",
    description=(
        "Администратор переводит магазин в статус blocked. Заблокированный магазин "
        "не должен создавать или изменять предложения на следующих этапах."
    ),
    tags=["Admin"],
    request=None,
    responses={
        200: OpenApiResponse(
            response=ShopSerializer,
            description="Магазин заблокирован.",
            examples=[
                OpenApiExample(
                    "Заблокированный магазин",
                    value={
                        "id": 4,
                        "name": "Procurement supplier",
                        "url": "https://supplier.example.com",
                        "owner": 10,
                        "status": "blocked",
                        "created_at": "2026-06-22T10:00:00Z",
                        "updated_at": "2026-06-22T10:10:00Z",
                    },
                    response_only=True,
                )
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

shop_profile_schema = extend_schema(
    operation_id="shop_profile_retrieve",
    summary="Профиль своего магазина",
    tags=["Shops"],
    responses={
        200: ShopSerializer,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

shop_profile_update_schema = extend_schema(
    operation_id="shop_profile_update",
    summary="Обновить профиль своего магазина",
    tags=["Shops"],
    request=ShopSerializer,
    responses={
        200: ShopSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

shop_offer_list_schema = extend_schema(
    operation_id="shop_offer_list",
    summary="Предложения своего магазина",
    tags=["Shops"],
    responses={
        200: OfferSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

shop_offer_create_schema = extend_schema(
    operation_id="shop_offer_create",
    summary="Создать предложение магазина",
    tags=["Shops"],
    request=ShopOfferCreateSerializer,
    responses={
        201: OfferSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

shop_offer_update_schema = extend_schema(
    operation_id="shop_offer_update",
    summary="Обновить предложение магазина",
    tags=["Shops"],
    request=ShopOfferUpdateSerializer,
    responses={
        200: OfferSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

shop_order_item_list_schema = extend_schema(
    operation_id="shop_order_item_list",
    summary="Позиции заказов своего магазина",
    tags=["Shops"],
    responses={
        200: OrderItemSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

shop_order_item_update_schema = extend_schema(
    operation_id="shop_order_item_update",
    summary="Обновить статус позиции заказа магазином",
    tags=["Shops"],
    request=ShopOrderItemUpdateSerializer,
    responses={
        200: OrderItemSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_user_list_schema = extend_schema(
    operation_id="admin_user_list",
    summary="Список пользователей",
    tags=["Admin"],
    responses={
        200: UserSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_user_update_schema = extend_schema(
    operation_id="admin_user_update",
    summary="Обновить пользователя",
    tags=["Admin"],
    request=AdminUserUpdateSerializer,
    responses={
        200: UserSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_shop_list_schema = extend_schema(
    operation_id="admin_shop_list",
    summary="Список магазинов",
    tags=["Admin"],
    responses={
        200: ShopSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_shop_update_schema = extend_schema(
    operation_id="admin_shop_update",
    summary="Обновить магазин",
    tags=["Admin"],
    request=AdminShopUpdateSerializer,
    responses={
        200: ShopSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_category_list_schema = extend_schema(
    operation_id="admin_category_list",
    summary="Список категорий",
    tags=["Admin"],
    responses={
        200: CategorySerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_category_create_schema = extend_schema(
    operation_id="admin_category_create",
    summary="Создать категорию",
    tags=["Admin"],
    request=CategorySerializer,
    responses={
        201: CategorySerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_category_update_schema = extend_schema(
    operation_id="admin_category_update",
    summary="Обновить категорию",
    tags=["Admin"],
    request=CategorySerializer,
    responses={
        200: CategorySerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_product_list_schema = extend_schema(
    operation_id="admin_product_list",
    summary="Список товаров",
    tags=["Admin"],
    responses={
        200: ProductSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_product_create_schema = extend_schema(
    operation_id="admin_product_create",
    summary="Создать товар",
    tags=["Admin"],
    request=ProductSerializer,
    responses={
        201: ProductSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_product_update_schema = extend_schema(
    operation_id="admin_product_update",
    summary="Обновить товар",
    tags=["Admin"],
    request=ProductSerializer,
    responses={
        200: ProductSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_parameter_list_schema = extend_schema(
    operation_id="admin_parameter_list",
    summary="Список параметров",
    tags=["Admin"],
    responses={
        200: ParameterSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_parameter_create_schema = extend_schema(
    operation_id="admin_parameter_create",
    summary="Создать параметр",
    tags=["Admin"],
    request=ParameterSerializer,
    responses={
        201: ParameterSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_parameter_update_schema = extend_schema(
    operation_id="admin_parameter_update",
    summary="Обновить параметр",
    tags=["Admin"],
    request=ParameterSerializer,
    responses={
        200: ParameterSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_offer_list_schema = extend_schema(
    operation_id="admin_offer_list",
    summary="Список предложений магазинов",
    tags=["Admin"],
    responses={
        200: OfferSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_offer_update_schema = extend_schema(
    operation_id="admin_offer_update",
    summary="Обновить предложение",
    tags=["Admin"],
    request=AdminOfferUpdateSerializer,
    responses={
        200: OfferSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_order_list_schema = extend_schema(
    operation_id="admin_order_list",
    summary="Список заказов",
    tags=["Admin"],
    responses={
        200: OrderDetailSerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

admin_order_update_schema = extend_schema(
    operation_id="admin_order_update",
    summary="Обновить заказ",
    tags=["Admin"],
    request=AdminOrderUpdateSerializer,
    responses={
        200: OrderDetailSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

admin_order_item_update_schema = extend_schema(
    operation_id="admin_order_item_update",
    summary="Обновить позицию заказа",
    tags=["Admin"],
    request=AdminOrderItemUpdateSerializer,
    responses={
        200: OrderItemSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

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
        "Итоговое количество не может превышать доступный остаток ProductInfo.quantity - reserved_quantity."
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
    summary="Отменить заказ покупателем",
    description=(
        "Покупатель может перевести свой заказ только в canceled и только до "
        "начала обработки магазином. Произвольные статусы заказа меняются через "
        "shop/admin endpoints."
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
            "Отменить заказ",
            value={"state": "canceled"},
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
