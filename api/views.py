from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.management.email_service import send_order_confirmation

from .filters import ProductFilter
from .models import Contact, Order, OrderItem, Product, ProductInfo
from .serializers import (
    AddToBasketSerializer,
    BasketItemResponseSerializer,
    ContactListResponseSerializer,
    ContactResponseSerializer,
    ContactSerializer,
    DeleteBasketItemSerializer,
    ErrorDetailSerializer,
    OrderConfirmResponseSerializer,
    OrderConfirmSerializer,
    OrderHistorySerializer,
    OrderItemSerializer,
    OrderSerializer,
    OrderUpdateSerializer,
    PaginatedOrderHistoryResponseSerializer,
    PaginatedProductResponseSerializer,
    ProductInfoSerializer,
    ProductSerializer,
)

# 1. Общие схемы OpenAPI ----
AUTH_REQUIRED_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description="JWT access token не передан, просрочен или некорректен.",
)
NOT_FOUND_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description="Запрошенный объект не найден или не принадлежит текущему пользователю.",
)
VALIDATION_ERROR_RESPONSE = OpenApiResponse(
    response=OpenApiTypes.OBJECT,
    description="Ошибка валидации. Ответ содержит поля запроса и список ошибок по каждому полю.",
)
BASKET_LIST_RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "array",
        "items": {"$ref": "#/components/schemas/OrderItem"},
    },
}


# 2. Каталог товаров ----
class ProductListView(APIView):
    """
    Просмотр списка продуктов
    """

    serializer_class = ProductSerializer

    class Pagination(PageNumberPagination):
        page_size = 5
        page_size_query_param = "page_size"
        max_page_size = 100

    @extend_schema(
        operation_id="product_list",
        summary="Список товаров",
        description=(
            "Возвращает постраничный каталог товаров. Фильтры по цене, магазину и "
            "характеристикам применяются к связанным предложениям ProductInfo, но "
            "в ответе возвращаются сами товары Product."
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
                description="ID магазина, в котором должен быть товар в наличии",
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
                description="Фильтр по параметру в формате 'имя_параметра:значение', например: 'цвет:красный'",
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
    ## 2.1. Список продуктов ----
    def get(self, request: Request):
        queryset = Product.objects.order_by("id")
        parameter = request.query_params.get("parameter")
        if parameter and ":" not in parameter:
            return Response(
                {"parameter": ["Ожидаемый формат: имя_параметра:значение."]},
                status=400,
            )

        filter_set = ProductFilter(request.query_params, queryset=queryset)
        if not filter_set.is_valid():
            return Response(filter_set.errors, status=400)
        queryset = filter_set.qs

        paginator = self.Pagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


## 2.2. Детальная информация о предложении ----
class ProductDetailView(APIView):
    serializer_class = ProductInfoSerializer

    @extend_schema(
        operation_id="product_offer_retrieve",
        summary="Детальная информация о предложении",
        description=(
            "Возвращает конкретное предложение товара ProductInfo: товар, магазин, "
            "название предложения, остаток, цену и рекомендованную цену."
        ),
        tags=["Products"],
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
    ## 2.2. Получить предложение ----
    def get(self, _, pk):
        product_info = get_object_or_404(ProductInfo, pk=pk)
        serializer = ProductInfoSerializer(product_info)
        return Response(serializer.data)


# 3. Корзина ----
class BasketView(APIView):
    """
    Взаимодействие с корзиной
    """

    serializer_class = OrderItemSerializer

    @extend_schema(
        operation_id="basket_retrieve",
        summary="Получить корзину",
        description=(
            "Возвращает все заказы текущего пользователя в статусе basket. "
            "Фактический формат ответа: массив заказов, где каждый заказ представлен "
            "массивом позиций OrderItem. Если корзина пуста, возвращается пустой массив."
        ),
        tags=["Basket"],
        responses={
            200: OpenApiResponse(
                response=BASKET_LIST_RESPONSE_SCHEMA,
                description="Список корзин и их позиций.",
                examples=[
                    OpenApiExample(
                        "Корзина с одной позицией",
                        value=[
                            [
                                {
                                    "id": 1,
                                    "quantity": 2,
                                    "order": 1,
                                    "product_info": 1,
                                }
                            ]
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
    ## 3.1. Получить корзину ----
    def get(self, request: Request):
        orders = Order.objects.filter(
            user=request.user,
            state="basket",
        ).order_by("id")
        result = []
        for order in orders:
            result.append(
                OrderItemSerializer(
                    OrderItem.objects.filter(order=order),
                    many=True,
                ).data
            )
        return Response(
            data=result,
            status=200,
        )

    @extend_schema(
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
    ## 3.2. Добавить товар в корзину ----
    def post(self, request: Request):
        serializer = AddToBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_info_id = serializer.validated_data["product_info_id"]
        quantity = serializer.validated_data["quantity"]

        product_info = get_object_or_404(ProductInfo, id=product_info_id)
        order = Order.objects.filter(user=request.user, state="basket").first()
        current_quantity = 0
        if order:
            current_quantity = (
                OrderItem.objects.filter(order=order, product_info=product_info)
                .values_list("quantity", flat=True)
                .first()
                or 0
            )

        if current_quantity + quantity > product_info.quantity:
            raise ValidationError(
                {
                    "quantity": (
                        "Запрошенное количество превышает доступный остаток. "
                        f"Доступно: {product_info.quantity}, уже в корзине: "
                        f"{current_quantity}."
                    )
                }
            )

        if not order:
            order = Order.objects.create(user=request.user, state="basket")

        order_item, created = OrderItem.objects.get_or_create(
            order=order,
            product_info=product_info,
            defaults={"quantity": quantity},
        )

        if not created:
            order_item.quantity += quantity
            order_item.save()

        serializer = OrderItemSerializer(order_item)

        return Response(
            data={
                "data": serializer.data,
            },
            status=200,
        )

    @extend_schema(
        operation_id="basket_delete_item",
        summary="Удалить позицию из корзины",
        description=(
            "Удаляет позицию OrderItem из корзины текущего пользователя. "
            "Основной параметр для удаления: item_id. Старое имя product_info_id "
            "временно поддерживается как алиас для обратной совместимости."
        ),
        tags=["Basket"],
        parameters=[
            OpenApiParameter(
                name="item_id",
                type=OpenApiTypes.INT,
                required=False,
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
                required=True,
                location=OpenApiParameter.QUERY,
                description="ID заказа-корзины, из которого удаляется позиция.",
            ),
        ],
        responses={
            204: OpenApiResponse(description="Позиция удалена, тело ответа пустое."),
            400: VALIDATION_ERROR_RESPONSE,
            401: AUTH_REQUIRED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
        },
    )
    ## 3.3. Удалить товар из корзины ----
    def delete(self, request: Request):
        serializer = DeleteBasketItemSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]
        item_id = (
            serializer.validated_data.get("item_id")
            or serializer.validated_data["product_info_id"]
        )

        order = get_object_or_404(Order, id=order_id, user=request.user, state="basket")

        order_item = get_object_or_404(OrderItem, id=item_id, order=order)
        order_item.delete()

        return Response(status=204)


# 4. Взаимодействие с адресом доставки ----
class ContactView(APIView):
    """
    Взаимодействие с адресом доставки
    """

    serializer_class = ContactSerializer

    @extend_schema(
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
    ## 4.1. Получить адреса доставки ----
    def get(self, request: Request):
        items = Contact.objects.filter(user=request.user).order_by("id")
        serializer = self.serializer_class(items, many=True)

        return Response(
            data={
                "data": serializer.data,
            },
            status=200,
        )

    @extend_schema(
        operation_id="contact_create",
        summary="Создать адрес доставки",
        description=(
            "Создает адрес доставки для текущего пользователя. Поля city, street и phone "
            "обязательны; house, structure, building и apartment могут быть пустыми строками."
        ),
        tags=["Contacts"],
        request=ContactSerializer,
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
    ## 4.2. Создать адрес доставки ----
    def post(self, request: Request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_contact = Contact(user=request.user, **serializer.validated_data)
        new_contact.save()

        serializer = self.serializer_class(new_contact)
        return Response(
            data={
                "data": serializer.data,
            },
            status=200,
        )

    @extend_schema(
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
    ## 4.3. Удалить адрес доставки ----
    def delete(self, request: Request):
        contact_id = request.GET.get("id")

        contact = get_object_or_404(Contact, id=contact_id, user=request.user)
        contact.delete()

        return Response(status=204)


# 5. Подтверждение заказа (изменение его статуса) ----
class OrderConfirmView(APIView):
    """
    Подтверждение заказа
    """

    @extend_schema(
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
    ## 5.1. Подтвердить заказ ----
    def post(self, request: Request):
        serializer = OrderConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data["order_id"]
        contact_id = serializer.validated_data["contact_id"]

        order = get_object_or_404(Order, id=order_id, user=request.user, state="basket")
        if not OrderItem.objects.filter(order=order).exists():
            raise ValidationError(
                {"order_id": "Нельзя подтвердить заказ без позиций в корзине."}
            )

        contact = get_object_or_404(Contact, id=contact_id, user=request.user)

        order.state = "confirmed"
        order.contact = contact
        order.save()

        send_order_confirmation(order)

        return Response({"status": "Order confirmed"}, status=200)


# 6. Список заказов (история заказов) ----
class OrderListView(APIView):
    """
    История заказов
    """

    class Pagination(PageNumberPagination):
        page_size = 5
        page_size_query_param = "page_size"
        max_page_size = 100

    @extend_schema(
        operation_id="order_history_list",
        summary="История заказов",
        description=(
            "Возвращает постраничную историю заказов текущего пользователя. "
            "Заказы в статусе basket не включаются. total_sum рассчитывается как "
            "сумма quantity * price по позициям заказа."
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
                    )
                ],
            ),
            401: AUTH_REQUIRED_RESPONSE,
        },
    )
    ## 6.1. Получить историю заказов ----
    def get(self, request: Request):
        pagination = self.Pagination()
        orders = (
            Order.objects.filter(user=request.user)
            .exclude(state="basket")
            .order_by("id")
        )
        queryset = pagination.paginate_queryset(queryset=orders, request=request)
        serializer = OrderHistorySerializer(queryset, many=True)
        return pagination.get_paginated_response(serializer.data)


# 7. Детальная информация о заказе ----
class OrderDetailView(APIView):
    serializer_class = OrderSerializer

    @extend_schema(
        operation_id="order_retrieve",
        summary="Детальная информация о заказе",
        description="Возвращает заказ по id, если он принадлежит текущему пользователю.",
        tags=["Orders"],
        responses={
            200: OpenApiResponse(
                response=OrderSerializer,
                description="Данные заказа.",
                examples=[
                    OpenApiExample(
                        "Заказ",
                        value={
                            "id": 1,
                            "user": 2,
                            "dt": "2026-06-21T16:40:31.083167Z",
                            "state": "confirmed",
                        },
                        response_only=True,
                    )
                ],
            ),
            401: AUTH_REQUIRED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
        },
    )
    ## 7.1. Получить заказ ----
    def get(self, request: Request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    @extend_schema(
        operation_id="order_update",
        summary="Обновить заказ",
        description=(
            "Частично обновляет заказ текущего пользователя. Текущая serializer-валидация "
            "разрешает передать только state=new."
        ),
        tags=["Orders"],
        request=OrderUpdateSerializer,
        responses={
            200: OpenApiResponse(
                response=OrderSerializer,
                description="Обновленный заказ.",
                examples=[
                    OpenApiExample(
                        "Заказ после PATCH",
                        value={
                            "id": 1,
                            "user": 2,
                            "dt": "2026-06-21T16:40:31.083167Z",
                            "state": "new",
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
    ## 7.2. Обновить заказ ----
    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        serializer = OrderUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrderSerializer(order).data, status=200)


# 8. Запланированные расширения ----
# Поставщик сможет обновлять прайс, управлять приемом заказов и получать список
# оформленных заказов с товарами из своего прайс-листа.
