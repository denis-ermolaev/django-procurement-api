from django.shortcuts import get_list_or_404, get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.management.email_service import send_order_confirmation

from .filters import ProductFilter
from .models import Contact, Order, OrderItem, Product, ProductInfo
from .serializers import (
    AddToBasketSerializer,
    ContactSerializer,
    OrderConfirmSerializer,
    OrderHistorySerializer,
    OrderItemSerializer,
    OrderSerializer,
    OrderUpdateSerializer,
    ProductInfoSerializer,
    ProductSerializer,
)


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
        parameters=[
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Номер страницы",
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                description="От 5 до 100, кол-во данных на страницу",
            ),
            # Добавляем параметры фильтрации
            OpenApiParameter(
                name="search",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Поиск по названию товара (регистронезависимый)",
            ),
            OpenApiParameter(
                name="category_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="ID категории",
            ),
            OpenApiParameter(
                name="shop_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="ID магазина, в котором должен быть товар в наличии",
            ),
            OpenApiParameter(
                name="price_min",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Минимальная цена товара (в любом магазине)",
            ),
            OpenApiParameter(
                name="price_max",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Максимальная цена товара (в любом магазине)",
            ),
            OpenApiParameter(
                name="parameter",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Фильтр по параметру в формате 'имя_параметра:значение', например: 'цвет:красный'",
            ),
        ]
    )
    # 1. Список продуктов ----
    def get(self, request: Request):
        queryset = Product.objects.order_by("id")

        # Применяем фильтрацию
        filter_set = ProductFilter(request.query_params, queryset=queryset)
        if not filter_set.is_valid():
            return Response(filter_set.errors, status=400)
        queryset = filter_set.qs

        # Пагинация
        paginator = self.Pagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# 2. Детальная информация о продукте ----
class ProductDetailView(APIView):
    def get(self, _, pk):
        product_info = get_object_or_404(ProductInfo, pk=pk)
        serializer = ProductInfoSerializer(product_info)
        return Response(serializer.data)


# 3. Корзина ----
class BasketView(APIView):
    """
    Взаимодействие с корзиной
    """

    # serializer_class = CapsulesSerializer
    @extend_schema(
        responses={
            200: {
                "example": [
                    [
                        {"order": 1, "product": 1, "shop": 1, "quantity": 14},
                        {"order": 1, "product": 2, "shop": 1, "quantity": 9},
                    ],
                    [
                        {"order": 2, "product": 1, "shop": 1, "quantity": 14},
                        {"order": 2, "product": 2, "shop": 1, "quantity": 9},
                    ],
                ],
            }
        }
    )
    ## 3.1. Получить корзину ----
    def get(self, request: Request):
        orders = Order.objects.filter(
            user=request.user,
            state="basket",
        )
        result = []
        for order in orders:
            result.append(
                OrderItemSerializer(
                    OrderItem.objects.filter(
                        order=order,
                    ),
                    many=True,
                ).data
            )
        return Response(
            data=result,
            status=200,
        )

    @extend_schema(
        request=AddToBasketSerializer,
    )
    ## 3.2. Добавить товар в корзину ----
    def post(self, request: Request):
        serializer = AddToBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_info_id = serializer.validated_data["product_info_id"]
        quantity = serializer.validated_data["quantity"]

        # TODO: Если quantity больше, чем товаров в наличии -> ошибка
        order, _ = Order.objects.get_or_create(
            user=request.user,
            state="basket",
            defaults={"state": "basket"},  # поля, которые заполнятся при создании
        )

        product_info = get_object_or_404(ProductInfo, id=product_info_id)

        order_item, created = OrderItem.objects.get_or_create(
            order=order,
            product_info=product_info,
            defaults={"quantity": quantity},
        )

        if not created:
            # Если позиция уже была – увеличиваем количество
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
        parameters=[
            OpenApiParameter(
                name="product_info_id",
                type=int,
                required=True,
                location=OpenApiParameter.QUERY,
                description="id продукта для удаления из корзины",
            ),
            OpenApiParameter(
                name="order_id",
                type=int,
                required=True,
                location=OpenApiParameter.QUERY,
                description="id заказа, из которого удаляем",
            ),
        ],
    )
    ## 3.3. Удалить товар из корзины ----
    def delete(self, request: Request):
        product_info_id = request.GET.get("product_info_id")
        order_id = request.GET.get("order_id")

        order = get_object_or_404(Order, id=order_id, user=request.user)

        product_info = get_object_or_404(OrderItem, id=product_info_id, order=order)
        product_info.delete()

        return Response(status=204)


# 4. Взаимодействие с адресом доставки ----
class ContactView(APIView):
    """
    Взаимодействие с адресом доставки
    """

    serializer_class = ContactSerializer

    def get(self, request: Request):
        query = Contact.objects.filter(user=request.user)

        items = get_list_or_404(query)

        serializer = self.serializer_class(items, many=True)

        return Response(
            data={
                "data": serializer.data,
            },
            status=200,
        )

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
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                required=True,
                location=OpenApiParameter.QUERY,
                description="id информации доставки для удаления",
            ),
        ],
    )
    def delete(self, request: Request):
        id = request.GET.get("id")

        contact = get_object_or_404(Contact, id=id, user=request.user)
        contact.delete()

        return Response(status=204)


# 5. Подтверждение заказа (изменение его статуса) ----
class OrderConfirmView(APIView):
    """
    Подтверждение заказа
    """

    @extend_schema(
        request=OrderConfirmSerializer,
        responses={
            200: {"description": "Заказ подтверждён"},
            400: {"description": "Ошибка валидации"},
            404: {"description": "Заказ или контакт не найден"},
        },
    )
    def post(self, request: Request):
        serializer = OrderConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data["order_id"]
        contact_id = serializer.validated_data["contact_id"]

        # Проверяем, что заказ существует, принадлежит пользователю и имеет статус корзины
        order = get_object_or_404(Order, id=order_id, user=request.user, state="basket")

        # Проверяем, что контакт существует и принадлежит пользователю
        contact = get_object_or_404(Contact, id=contact_id, user=request.user)

        # Обновляем заказ: меняем статус и привязываем контакт
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
        responses={
            200: OrderHistorySerializer(many=True),
        }
    )
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


# 2. Детальная информация о продукте ----
class OrderDetailView(APIView):
    def get(self, request: Request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    @extend_schema(
        request=OrderUpdateSerializer,
        responses={
            200: OrderSerializer,
            400: {"description": "Ошибка валидации"},
            404: {"description": "Заказ не найден"},
        },
    )
    def patch(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        serializer = OrderUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Возвращаем полную информацию обновлённого заказа
        return Response(OrderSerializer(order).data, status=200)


# TODO: Поставщик:
# через API информирует сервис об обновлении прайса,
# может включать и отключать приём заказов,
# может получать список оформленных заказов (с товарами из его прайса).


# TODO: отправка накладной на email администратора (для исполнения заказа),
# TODO: отправка заказа на email клиента (подтверждение приёма заказа).
