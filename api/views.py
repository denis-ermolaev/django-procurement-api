# Create your views here.
from django.shortcuts import get_list_or_404, get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contact, Order, OrderItem, ProductInfo
from .serializers import (
    AddToBasketSerializer,
    ContactSerializer,
    OrderConfirmSerializer,
    OrderHistorySerializer,
    OrderItemSerializer,
    ProductInfoSerializer,
)


class CheckView(APIView):
    def get(self, _: Request):
        return Response(
            data={"message": "API успешно запущено и работает."},
            status=200,
        )


class ProductListView(APIView):
    serializer_class = ProductInfoSerializer

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
        ]
    )
    def get(self, request: Request):
        pagination = self.Pagination()

        product_info_list = ProductInfo.objects.all()
        queryset = pagination.paginate_queryset(
            queryset=product_info_list, request=request
        )

        serializer_product_info = self.serializer_class(queryset, many=True)
        return pagination.get_paginated_response(serializer_product_info.data)


class BasketView(APIView):
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
    def get(self, request: Request):
        orders = Order.objects.filter(user=request.user)
        result = []
        for order in orders:
            result.append(
                OrderItemSerializer(
                    OrderItem.objects.filter(order=order), many=True
                ).data
            )
        return Response(
            data=result,
            status=200,
        )

    @extend_schema(
        request=AddToBasketSerializer,
    )
    def post(self, request: Request):
        serializer = AddToBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_info_id = serializer.validated_data["product_info_id"]
        order_id = serializer.validated_data["order_id"]
        quantity = serializer.validated_data["quantity"]

        # TODO: Если quantity больше, чем товаров в наличии -> ошибка
        order, _ = Order.objects.get_or_create(
            id=order_id,
            user=request.user,
            defaults={"state": "basket"},  # поля, которые заполнятся при создании
        )

        # Получение товара и product_info
        product_info = ProductInfo.objects.get(id=product_info_id)

        # TODO: При повторном добавлении увеличивать quantity
        # а не добавлять новую запись
        order_item = OrderItem.objects.create(
            order=order,
            product_info=product_info,
            quantity=quantity,
        )
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
    # TODO: передеавать id через url по REST ?
    def delete(self, request: Request):
        product_info_id = request.GET.get("product_info_id")
        order_id = request.GET.get("order_id")

        order = get_object_or_404(Order, id=order_id, user=request.user)

        product_info = get_object_or_404(OrderItem, id=product_info_id, order=order)
        product_info.delete()

        return Response(status=204)
        # TODO: добавить отправление ошибки, если удалить не получилось


class ContactView(APIView):
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


class OrderConfirmView(APIView):
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
        order.state = "confirmed"  # или 'new' — по вашей логике
        order.contact = contact
        order.save()

        return Response({"status": "Order confirmed"}, status=200)


class OrderHistoryView(APIView):
    @extend_schema(
        responses={
            200: OrderHistorySerializer(many=True),
        }
    )
    def get(self, request: Request):
        orders = Order.objects.filter(user=request.user).exclude(
            state="basket"
        )  # исключаем корзины
        serializer = OrderHistorySerializer(orders, many=True)
        return Response(serializer.data, status=200)
