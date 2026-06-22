from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.openapi import (
    basket_add_schema,
    basket_delete_schema,
    basket_retrieve_schema,
    contact_create_schema,
    contact_delete_schema,
    contact_list_schema,
    order_confirm_schema,
    order_history_schema,
    order_retrieve_schema,
    order_update_schema,
    product_detail_schema,
    product_list_schema,
)
from api.services import basket as basket_service
from api.services import contacts as contact_service
from api.services import orders as order_service
from api.services import products as product_service

from .serializers import (
    AddToBasketSerializer,
    ContactSerializer,
    DeleteBasketItemSerializer,
    OrderConfirmSerializer,
    OrderDetailSerializer,
    OrderHistorySerializer,
    OrderItemSerializer,
    OrderUpdateSerializer,
    ProductInfoSerializer,
    ProductSerializer,
)


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

    @product_list_schema
    ## 2.1. Список продуктов ----
    def get(self, request: Request):
        queryset = product_service.get_filtered_products(
            request.user, request.query_params
        )
        paginator = self.Pagination()
        page = paginator.paginate_queryset(queryset, request)
        product_service.log_product_page_loaded(
            request.user,
            total_count=paginator.page.paginator.count,
            page_size=len(page),
        )
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


## 2.2. Детальная информация о предложении ----
class ProductDetailView(APIView):
    serializer_class = ProductInfoSerializer

    @product_detail_schema
    ## 2.2. Получить предложение ----
    def get(self, _, pk):
        product_info = product_service.get_product_info(pk)
        serializer = ProductInfoSerializer(product_info)
        return Response(serializer.data)


# 3. Корзина ----
class BasketView(APIView):
    """
    Взаимодействие с корзиной
    """

    serializer_class = OrderItemSerializer

    @basket_retrieve_schema
    ## 3.1. Получить корзину ----
    def get(self, request: Request):
        result = OrderItemSerializer(
            basket_service.get_basket_items(request.user),
            many=True,
        ).data
        return Response(
            data=result,
            status=200,
        )

    @basket_add_schema
    ## 3.2. Добавить товар в корзину ----
    def post(self, request: Request):
        serializer = AddToBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_item = basket_service.add_basket_item(
            request.user,
            product_info_id=serializer.validated_data["product_info_id"],
            quantity=serializer.validated_data["quantity"],
        )
        serializer = OrderItemSerializer(order_item)

        return Response(
            data={
                "data": serializer.data,
            },
            status=200,
        )

    @basket_delete_schema
    ## 3.3. Удалить товар из корзины ----
    def delete(self, request: Request):
        serializer = DeleteBasketItemSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data.get("order_id")
        item_id = (
            serializer.validated_data.get("item_id")
            or serializer.validated_data["product_info_id"]
        )
        basket_service.delete_basket_item(
            request.user,
            item_id=item_id,
            order_id=order_id,
        )

        return Response(status=204)


# 4. Взаимодействие с адресом доставки ----
class ContactView(APIView):
    """
    Взаимодействие с адресом доставки
    """

    serializer_class = ContactSerializer

    @contact_list_schema
    ## 4.1. Получить адреса доставки ----
    def get(self, request: Request):
        items = contact_service.get_user_contacts(request.user)
        serializer = self.serializer_class(items, many=True)

        return Response(
            data={
                "data": serializer.data,
            },
            status=200,
        )

    @contact_create_schema
    ## 4.2. Создать адрес доставки ----
    def post(self, request: Request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_contact = contact_service.create_contact(
            request.user,
            serializer.validated_data,
        )

        serializer = self.serializer_class(new_contact)
        return Response(
            data={
                "data": serializer.data,
            },
            status=200,
        )

    @contact_delete_schema
    ## 4.3. Удалить адрес доставки ----
    def delete(self, request: Request):
        contact_id = request.GET.get("id")
        contact_service.delete_contact(request.user, contact_id)

        return Response(status=204)


# 5. Подтверждение заказа (изменение его статуса) ----
class OrderConfirmView(APIView):
    """
    Подтверждение заказа
    """

    @order_confirm_schema
    ## 5.1. Подтвердить заказ ----
    def post(self, request: Request):
        serializer = OrderConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_service.confirm_order(
            request.user,
            order_id=serializer.validated_data["order_id"],
            contact_id=serializer.validated_data["contact_id"],
        )

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

    @order_history_schema
    ## 6.1. Получить историю заказов ----
    def get(self, request: Request):
        pagination = self.Pagination()
        orders = order_service.get_order_history(request.user)
        queryset = pagination.paginate_queryset(queryset=orders, request=request)
        serializer = OrderHistorySerializer(queryset, many=True)
        return pagination.get_paginated_response(serializer.data)


# 7. Детальная информация о заказе ----
class OrderDetailView(APIView):
    serializer_class = OrderDetailSerializer

    @order_retrieve_schema
    ## 7.1. Получить заказ ----
    def get(self, request: Request, pk):
        order = order_service.get_user_order(request.user, pk)
        serializer = self.serializer_class(order)
        return Response(serializer.data)

    @order_update_schema
    ## 7.2. Обновить заказ ----
    def patch(self, request, pk):
        order = order_service.get_user_order(request.user, pk)
        serializer = OrderUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        order = order_service.update_order_state(
            order,
            serializer.validated_data["state"],
        )
        return Response(self.serializer_class(order).data, status=200)


# 8. Запланированные расширения ----
# Поставщик сможет обновлять прайс, управлять приемом заказов и получать список
# оформленных заказов с товарами из своего прайс-листа.
