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
    BasketSerializer,
    BuyerOfferSerializer,
    CategorySerializer,
    ContactListResponseSerializer,
    ContactResponseSerializer,
    ContactSerializer,
    ErrorDetailSerializer,
    OfferSerializer,
    OrderConfirmSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    PaginatedAdminOrderResponseSerializer,
    PaginatedBuyerOfferResponseSerializer,
    PaginatedOfferResponseSerializer,
    PaginatedOrderHistoryResponseSerializer,
    PaginatedOrderItemResponseSerializer,
    PaginatedProductResponseSerializer,
    ParameterSerializer,
    ProductSerializer,
    ShopImportSerializer,
    ShopOfferCreateSerializer,
    ShopOfferUpdateSerializer,
    ShopOrderItemUpdateSerializer,
    ShopRegistrationResponseSerializer,
    ShopRegistrationSerializer,
    ShopSerializer,
    UpdateBasketItemSerializer,
    UserSerializer,
)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
#                              OPENAPI POSTPROCESSING HOOKS                    #
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #


def add_server_entry(result, generator, request, public):
    """POSTPROCESSING_HOOK — динамический Server entry для OpenAPI схемы.

    Swagger UI использует поле ``servers`` для построения base URL при
    выполнении запросов «Try It Out».  Без него запросы уходят на
    ``https://host:port/api/...`` без префикса ``/proxy/8000/``, который
    добавляет code-server, и получают 404.

    Хук подхватывает ``SCRIPT_NAME`` (установленный WSGI middleware
    :class:`~core.wsgi.ReverseProxyPrefix`) и строит полный URL вида:

        https://192.168.137.2:8080/proxy/8000/

    Если SCRIPT_NAME пуст (прямые запросы), сервер не добавляется — схема
    остаётся чистой (drf-spectacular по умолчанию не включает servers).
    """
    if request is None:
        return result

    script_name = getattr(request, "script_name", "") or request.META.get(
        "SCRIPT_NAME", ""
    )
    if not script_name:
        return result

    # Собираем вручную: scheme + host + script_name
    # build_absolute_uri('/') неприменим — urljoin заменит весь path,
    # потеряв SCRIPT_NAME.
    scheme = request.scheme
    host = request.get_host()
    server_url = f"{scheme}://{host}{script_name}/"

    if not any(s.get("url") == server_url for s in result.get("servers", [])):
        result.setdefault("servers", [])
        result["servers"].append({"url": server_url})

    return result


# ---------------------------------------------------------------------------- #

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

shop_import_status_schema = extend_schema(
    operation_id="shop_import_status",
    summary="Статус фонового импорта прайса",
    description="Возвращает текущий статус задачи импорта по её ID.",
    tags=["Shops"],
    parameters=[
        OpenApiParameter(
            name="pk",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="ID задачи импорта (ImportJob).",
        ),
    ],
    responses={
        200: OpenApiTypes.OBJECT,
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
        200: PaginatedOfferResponseSerializer,
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

shop_import_create_schema = extend_schema(
    operation_id="shop_import_create",
    summary="Импортировать YAML-прайс магазина",
    description=(
        "Асинхронный импорт прайса магазина. Endpoint принимает "
        "YAML-файл multipart-полем file или YAML-строку в JSON-поле content, "
        "запускает фоновую задачу и возвращает job_id для отслеживания статуса."
    ),
    tags=["Shops"],
    request=ShopImportSerializer,
    responses={
        202: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Импорт запущен фоново.",
            examples=[
                OpenApiExample(
                    "Задача создана",
                    value={"job_id": 1, "status": "processing"},
                    response_only=True,
                )
            ],
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

shop_order_item_list_schema = extend_schema(
    operation_id="shop_order_item_list",
    summary="Позиции заказов своего магазина",
    tags=["Shops"],
    responses={
        200: PaginatedOrderItemResponseSerializer,
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
            description="Количество пользователей на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по email, имени или фамилии пользователя (регистронезависимый).",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=UserSerializer(many=True),
            description="Постраничный список пользователей.",
        ),
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
            description="Количество магазинов на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по названию магазина или email владельца (регистронезависимый).",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=ShopSerializer(many=True),
            description="Постраничный список магазинов.",
        ),
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
            description="Количество категорий на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по названию категории (регистронезависимый).",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=CategorySerializer(many=True),
            description="Постраничный список категорий.",
        ),
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
            description="Поиск по названию товара (регистронезависимый).",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=ProductSerializer(many=True),
            description="Постраничный список товаров.",
        ),
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
            description="Количество параметров на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по названию параметра (регистронезависимый).",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=ParameterSerializer(many=True),
            description="Постраничный список параметров.",
        ),
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
            description="Количество предложений на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по названию предложения или товара (регистронезависимый).",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=OfferSerializer(many=True),
            description="Постраничный список предложений.",
        ),
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
    description=(
        "Возвращает постраничный список всех заказов в системе. "
        "Доступно только администраторам. Поддерживает поиск по email "
        "пользователя, ID заказа или городу доставки, а также фильтрацию "
        "по статусу заказа."
    ),
    tags=["Admin"],
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
            description="Количество заказов на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по email пользователя, ID заказа или городу доставки (регистронезависимый).",
        ),
        OpenApiParameter(
            name="status",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description=(
                "Фильтр по статусу заказа. Допустимые значения: "
                "confirmed, processing, sent, delivered, partially_canceled, canceled."
            ),
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PaginatedAdminOrderResponseSerializer,
            description="Постраничный список заказов.",
        ),
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

offer_list_schema = extend_schema(
    operation_id="offer_list",
    summary="Список доступных предложений",
    description=(
        "Возвращает покупательский список Offer/ProductInfo. В отличие от "
        "`/api/products/`, этот endpoint показывает конкретные предложения "
        "магазинов с ценой, остатком и характеристиками. Все фильтры применяются "
        "к одному и тому же ProductInfo."
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
            description="Количество предложений на страницу. Допустимый диапазон: 1-100.",
        ),
        OpenApiParameter(
            name="search",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Поиск по названию товара или предложения.",
        ),
        OpenApiParameter(
            name="category_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="ID категории товара.",
        ),
        OpenApiParameter(
            name="shop_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="ID магазина.",
        ),
        OpenApiParameter(
            name="price_min",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Минимальная цена предложения.",
        ),
        OpenApiParameter(
            name="price_max",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description="Максимальная цена предложения.",
        ),
        OpenApiParameter(
            name="parameter",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Фильтр по характеристике предложения в формате 'имя:значение'.",
        ),
        OpenApiParameter(
            name="in_stock",
            type=OpenApiTypes.BOOL,
            location=OpenApiParameter.QUERY,
            description="Если true, возвращаются только предложения с доступным остатком.",
        ),
        OpenApiParameter(
            name="ordering",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description="Сортировка: id, -id, price, -price, quantity, -quantity.",
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PaginatedBuyerOfferResponseSerializer,
            description="Постраничный список предложений.",
            examples=[
                OpenApiExample(
                    "Предложения",
                    value={
                        "count": 1,
                        "next": None,
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "offer_id": 1,
                                "product_id": 1,
                                "product_name": "Смартфон",
                                "offer_name": "Смартфон 128GB",
                                "shop_id": 1,
                                "shop_name": "Main shop",
                                "quantity": 10,
                                "available_quantity": 8,
                                "price": 1000,
                                "price_rrc": 1200,
                                "status": "active",
                                "parameters": [
                                    {"name": "цвет", "value": "черный"},
                                ],
                                "can_add_to_basket": True,
                            }
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

offer_detail_schema = extend_schema(
    operation_id="offer_retrieve",
    summary="Карточка предложения",
    description=(
        "Возвращает конкретное доступное к покупке предложение магазина. "
        "Недоступные, архивные, заблокированные предложения и предложения "
        "неактивных магазинов скрываются через 404."
    ),
    tags=["Products"],
    responses={
        200: BuyerOfferSerializer,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

product_offers_schema = extend_schema(
    operation_id="product_offer_list",
    summary="Предложения товара",
    description=(
        "Возвращает доступные предложения конкретного общего товара Product. "
        "Если сам Product или его категория неактивны, endpoint возвращает 404."
    ),
    tags=["Products"],
    responses={
        200: PaginatedBuyerOfferResponseSerializer,
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

basket_retrieve_schema = extend_schema(
    operation_id="basket_retrieve",
    summary="Получить корзину",
    description=(
        "Возвращает объект текущей корзины пользователя: ID basket-заказа, позиции, "
        "суммы строк, общий total и предупреждения о недоступных предложениях. "
        "Если корзина еще не создана, id будет null, items - пустым списком."
    ),
    tags=["Basket"],
    responses={
        200: OpenApiResponse(
            response=BasketSerializer,
            description="Объект текущей корзины.",
            examples=[
                OpenApiExample(
                    "Корзина с одной позицией",
                    value={
                        "id": 1,
                        "state": "basket",
                        "items": [
                            {
                                "id": 1,
                                "offer_id": 10,
                                "product_name": "Смартфон",
                                "offer_name": "Смартфон 128GB",
                                "shop_name": "Main shop",
                                "unit_price": 1000,
                                "quantity": 2,
                                "line_total": 2000,
                                "available_quantity": 8,
                                "state": "basket",
                                "warnings": [],
                                "is_available": True,
                            }
                        ],
                        "total": 2000,
                    },
                    response_only=True,
                ),
                OpenApiExample(
                    "Пустая корзина",
                    value={"id": None, "state": "basket", "items": [], "total": 0},
                    response_only=True,
                ),
            ],
        ),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
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
        "обязательны; house, structure, building и apartment могут быть пустыми строками. "
        "Ответ возвращается в обертке data."
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
        201: OpenApiResponse(
            response=ContactResponseSerializer,
            description="Адрес доставки создан.",
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

# contact_delete_schema удалён — удаление только через DELETE /contacts/{pk}/

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
            response=OrderDetailSerializer,
            description="Заказ подтвержден, возвращены детали оформленного заказа.",
            examples=[
                OpenApiExample(
                    "Заказ подтвержден",
                    value={
                        "id": 1,
                        "user": 2,
                        "dt": "2026-06-21T16:40:31.083167Z",
                        "confirmed_at": "2026-06-21T16:41:00.000000Z",
                        "state": "confirmed",
                        "contact": 3,
                        "cancellation_reason": "",
                        "total_sum": 2000,
                        "items": [
                            {
                                "id": 10,
                                "order": 1,
                                "product_info": 1,
                                "quantity": 2,
                                "state": "confirmed",
                                "unit_price": 1000,
                            }
                        ],
                    },
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


category_list_schema = extend_schema(
    operation_id="category_list",
    summary="Список активных категорий",
    description=(
        "Возвращает список активных категорий, в которых есть хотя бы одно "
        "активное предложение от активного магазина. Категории без активных "
        "предложений не включаются."
    ),
    tags=["Products"],
    responses={
        200: CategorySerializer(many=True),
        401: AUTH_REQUIRED_RESPONSE,
    },
)

order_cancel_schema = extend_schema(
    operation_id="order_cancel",
    summary="Отменить заказ покупателем",
    description=(
        "Покупатель может отменить свой заказ, если он ещё не начал "
        "обрабатываться магазином. Переводит заказ и все его позиции в "
        "статус canceled."
    ),
    tags=["Orders"],
    request=None,
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
            description="Заказ отменён.",
            examples=[
                OpenApiExample(
                    "Отменённый заказ",
                    value={
                        "id": 1,
                        "user": 2,
                        "dt": "2026-06-21T16:40:31.083167Z",
                        "state": "canceled",
                        "contact": 3,
                        "total_sum": 0,
                        "items": [],
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

health_check_schema = extend_schema(
    operation_id="health_check",
    summary="Проверка работоспособности сервиса",
    description="Возвращает статус сервиса и подключения к базе данных. Не требует аутентификации.",
    tags=["Health"],
    auth=None,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Сервис работает, БД подключена.",
            examples=[
                OpenApiExample(
                    "OK",
                    value={"status": "ok", "db": "connected"},
                    response_only=True,
                )
            ],
        ),
        503: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="БД недоступна.",
            examples=[
                OpenApiExample(
                    "DB unavailable",
                    value={"status": "ok", "db": "disconnected"},
                    response_only=True,
                )
            ],
        ),
    },
)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
#        СХЕМЫ ДЛЯ BASKET И CONTACT (ранее не имели отдельных декораторов)       #
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
basket_clear_schema = extend_schema(
    operation_id="basket_clear",
    summary="Очистить корзину",
    description=(
        "Удаляет все позиции из текущей корзины пользователя. Если корзина "
        "не создана или уже пуста, возвращает 204 без ошибки."
    ),
    tags=["Basket"],
    request=None,
    responses={
        204: OpenApiResponse(description="Корзина очищена."),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
    },
)

basket_item_add_schema = extend_schema(
    operation_id="basket_item_add",
    summary="Добавить позицию в корзину",
    description=(
        "Добавляет предложение (offer) в корзину текущего пользователя. "
        "Если такое предложение уже есть в корзине, увеличивает количество. "
        "Если корзина ещё не создана, создаёт новый basket-заказ. Проверяется "
        "доступный остаток с учётом уже зарезервированного."
    ),
    tags=["Basket"],
    request=AddToBasketSerializer,
    responses={
        201: OpenApiResponse(
            response=BasketItemResponseSerializer,
            description="Позиция добавлена в корзину.",
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

basket_item_update_schema = extend_schema(
    operation_id="basket_item_update",
    summary="Изменить количество позиции в корзине",
    description=(
        "Обновляет количество указанной позиции в корзине текущего "
        "пользователя. Позиция должна принадлежать basket-заказу пользователя. "
        "Новое количество не должно превышать доступный остаток."
    ),
    tags=["Basket"],
    request=UpdateBasketItemSerializer,
    responses={
        200: OpenApiResponse(
            response=BasketItemResponseSerializer,
            description="Количество позиции обновлено.",
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

basket_item_delete_schema = extend_schema(
    operation_id="basket_item_delete",
    summary="Удалить позицию из корзины",
    description=(
        "Удаляет указанную позицию из корзины текущего пользователя. "
        "Позиция должна принадлежать basket-заказу пользователя."
    ),
    tags=["Basket"],
    request=None,
    responses={
        204: OpenApiResponse(description="Позиция удалена из корзины."),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

contact_detail_schema = extend_schema(
    operation_id="contact_retrieve",
    summary="Получить адрес доставки",
    description=(
        "Возвращает адрес доставки текущего пользователя по ID в обертке data. "
        "Адрес должен принадлежать текущему пользователю."
    ),
    tags=["Contacts"],
    responses={
        200: OpenApiResponse(
            response=ContactResponseSerializer,
            description="Адрес доставки в обертке data.",
        ),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

contact_update_schema = extend_schema(
    operation_id="contact_update",
    summary="Обновить адрес доставки",
    description="Обновляет адрес доставки текущего пользователя. Все поля опциональны.",
    tags=["Contacts"],
    request=ContactSerializer,
    responses={
        200: OpenApiResponse(
            response=ContactSerializer,
            description="Обновлённый адрес доставки.",
        ),
        400: VALIDATION_ERROR_RESPONSE,
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)

# ---------------------------------------------------------------------------- #

contact_delete_schema = extend_schema(
    operation_id="contact_delete",
    summary="Удалить адрес доставки",
    description=(
        "Удаляет адрес доставки текущего пользователя. Если адрес используется "
        "в оформленных заказах (не корзинах), выполняется soft-delete: "
        "поле is_deleted устанавливается в True, сам контакт остаётся в базе."
    ),
    tags=["Contacts"],
    responses={
        204: OpenApiResponse(description="Адрес доставки удалён."),
        401: AUTH_REQUIRED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
