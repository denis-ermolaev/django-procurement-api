import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import ImportJob, Shop
from api.openapi import (
    admin_category_create_schema,
    admin_category_list_schema,
    admin_category_update_schema,
    admin_offer_list_schema,
    admin_offer_update_schema,
    admin_order_item_update_schema,
    admin_order_list_schema,
    admin_order_update_schema,
    admin_parameter_create_schema,
    admin_parameter_list_schema,
    admin_parameter_update_schema,
    admin_product_create_schema,
    admin_product_list_schema,
    admin_product_update_schema,
    admin_shop_approve_schema,
    admin_shop_block_schema,
    admin_shop_list_schema,
    admin_shop_update_schema,
    admin_user_list_schema,
    admin_user_update_schema,
    basket_clear_schema,
    basket_item_add_schema,
    basket_item_delete_schema,
    basket_item_update_schema,
    basket_retrieve_schema,
    category_list_schema,
    contact_create_schema,
    contact_delete_schema,
    contact_detail_schema,
    contact_list_schema,
    contact_update_schema,
    health_check_schema,
    offer_detail_schema,
    offer_list_schema,
    order_cancel_schema,
    order_confirm_schema,
    order_history_schema,
    order_retrieve_schema,
    product_list_schema,
    product_offers_schema,
    shop_import_create_schema,
    shop_import_status_schema,
    shop_offer_create_schema,
    shop_offer_list_schema,
    shop_offer_update_schema,
    shop_order_item_list_schema,
    shop_order_item_update_schema,
    shop_profile_schema,
    shop_profile_update_schema,
    shop_register_schema,
)
from api.permissions import IsActiveShop, IsAdminUserType, IsBuyer, IsShop
from api.services import admin_api as admin_service
from api.services import basket as basket_service
from api.services import contacts as contact_service
from api.services import orders as order_service
from api.services import products as product_service
from api.services import shop_data as shop_data_service
from api.services import shops as shop_service
from api.throttles import (
    ConfirmOrderRateThrottle,
    ImportRateThrottle,
    ShopRegisterRateThrottle,
)

from .serializers import (
    AddToBasketSerializer,
    AdminOfferUpdateSerializer,
    AdminOrderItemUpdateSerializer,
    AdminOrderUpdateSerializer,
    AdminShopUpdateSerializer,
    AdminUserUpdateSerializer,
    BasketItemSummarySerializer,
    BasketSerializer,
    BuyerOfferSerializer,
    CategorySerializer,
    ContactSerializer,
    OfferSerializer,
    OrderConfirmSerializer,
    OrderDetailSerializer,
    OrderHistorySerializer,
    OrderItemSerializer,
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

logger = logging.getLogger(__name__)


class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# 1. Health-check ----
class HealthCheckView(APIView):
    """Проверка работоспособности сервиса."""

    permission_classes = [AllowAny]

    @health_check_schema
    def get(self, request: Request) -> Response:
        from django.db import connection
        from django.db.utils import OperationalError

        db_status = "connected"
        try:
            connection.ensure_connection()
        except OperationalError:
            db_status = "disconnected"

        status_code = (
            status.HTTP_200_OK
            if db_status == "connected"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response({"status": "ok", "db": db_status}, status=status_code)


# 2. Магазины ----
class ShopRegistrationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ShopRegisterRateThrottle]
    serializer_class = ShopRegistrationSerializer

    @shop_register_schema
    ## 2.1. Зарегистрировать магазин ----
    def post(self, request: Request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, shop = shop_service.register_shop(serializer.validated_data)
        response_serializer = ShopRegistrationResponseSerializer(
            {"user": user, "shop": shop}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class AdminShopApproveView(APIView):
    permission_classes = [IsAdminUserType]
    serializer_class = ShopSerializer

    @admin_shop_approve_schema
    ## 2.2. Одобрить магазин ----
    def post(self, request: Request, pk: int):
        shop = shop_service.approve_shop(request.user, shop_id=pk)
        serializer = self.serializer_class(shop)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminShopBlockView(APIView):
    permission_classes = [IsAdminUserType]
    serializer_class = ShopSerializer

    @admin_shop_block_schema
    ## 2.3. Заблокировать магазин ----
    def post(self, request: Request, pk: int):
        shop = shop_service.block_shop(request.user, shop_id=pk)
        serializer = self.serializer_class(shop)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ShopProfileView(APIView):
    permission_classes = [IsShop]
    serializer_class = ShopSerializer

    @shop_profile_schema
    ## 2.4. Получить профиль магазина ----
    def get(self, request: Request):
        shop = shop_service.get_user_shop(request.user)
        serializer = self.serializer_class(shop)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @shop_profile_update_schema
    ## 2.5. Обновить профиль магазина ----
    def patch(self, request: Request):
        serializer = self.serializer_class(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        shop = shop_service.update_user_shop(request.user, serializer.validated_data)
        return Response(self.serializer_class(shop).data, status=status.HTTP_200_OK)


class ShopOfferListCreateView(APIView):
    serializer_class = OfferSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsShop()]
        return [IsActiveShop()]

    @shop_offer_list_schema
    ## 2.6. Получить предложения магазина ----
    def get(self, request: Request):
        offers = shop_service.get_shop_offers(request.user)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(offers, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @shop_offer_create_schema
    ## 2.7. Создать предложение магазина ----
    def post(self, request: Request):
        serializer = ShopOfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offer = shop_service.create_shop_offer(request.user, serializer.validated_data)
        return Response(OfferSerializer(offer).data, status=status.HTTP_201_CREATED)


class ShopOfferDetailView(APIView):
    permission_classes = [IsActiveShop]

    @shop_offer_update_schema
    ## 2.8. Обновить предложение магазина ----
    def patch(self, request: Request, pk: int):
        serializer = ShopOfferUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        offer = shop_service.update_shop_offer(
            request.user,
            product_info_id=pk,
            offer_data=serializer.validated_data,
        )
        return Response(OfferSerializer(offer).data, status=status.HTTP_200_OK)


class ShopImportView(APIView):
    permission_classes = [IsActiveShop]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = ShopImportSerializer
    throttle_classes = [ImportRateThrottle]

    @shop_import_create_schema
    ## 2.9. Импортировать прайс магазина (фоново через RQ) ----
    def post(self, request: Request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data.get("content")
        uploaded_file = serializer.validated_data.get("file")
        if uploaded_file is not None:
            content = uploaded_file.read().decode("utf-8")

        shop = Shop.objects.get(owner=request.user)
        import_job = ImportJob.objects.create(shop=shop, status="processing")

        shop_data_service.import_shop_data_async.delay(
            user_id=request.user.pk,
            import_job_id=import_job.pk,
            content=content,
        )

        logger.info(
            "[ShopImportView] shop_import_started_async user_id=%s job_id=%s",
            request.user.pk,
            import_job.pk,
        )
        return Response(
            {"job_id": import_job.pk, "status": "processing"},
            status=status.HTTP_202_ACCEPTED,
        )


class ShopImportStatusView(APIView):
    """Проверка статуса фонового импорта прайса."""

    permission_classes = [IsShop]

    @shop_import_status_schema
    def get(self, request: Request, pk: int):
        job = get_object_or_404(ImportJob, pk=pk, shop__owner=request.user)
        error_log = job.error_log if job.status == "failed" else ""
        return Response(
            {
                "id": job.pk,
                "status": job.status,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
                "stats": job.stats,
                "error_log": error_log,
            },
            status=status.HTTP_200_OK,
        )


class ShopOrderItemListView(APIView):
    permission_classes = [IsShop]
    serializer_class = OrderItemSerializer

    @shop_order_item_list_schema
    ## 2.10. Получить позиции заказов магазина ----
    def get(self, request: Request):
        items = order_service.get_shop_order_items(request.user)
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(items, request)
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ShopOrderItemDetailView(APIView):
    permission_classes = [IsShop]

    @shop_order_item_update_schema
    ## 2.11. Обновить статус позиции заказа ----
    def patch(self, request: Request, pk: int):
        serializer = ShopOrderItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = order_service.update_shop_order_item_state(
            request.user,
            item_id=pk,
            new_state=serializer.validated_data["state"],
        )
        return Response(OrderItemSerializer(item).data, status=status.HTTP_200_OK)


# 2. Справочники ----
class CategoryListView(APIView):
    """Список активных категорий."""

    serializer_class = CategorySerializer

    @category_list_schema
    def get(self, request: Request):
        queryset = product_service.get_active_categories()
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


# 3. Каталог товаров ----
class ProductListView(APIView):
    """
    Просмотр списка продуктов
    """

    serializer_class = ProductSerializer

    @product_list_schema
    ## 2.1. Список продуктов ----
    def get(self, request: Request):
        queryset = product_service.get_filtered_products(
            request.user, request.query_params
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request)
        product_service.log_product_page_loaded(
            request.user,
            total_count=paginator.page.paginator.count,
            page_size=len(page),
        )
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class OfferListView(APIView):
    serializer_class = BuyerOfferSerializer

    @offer_list_schema
    ## 2.2. Список предложений ----
    def get(self, request: Request):
        queryset = product_service.get_available_offers(
            request.user,
            request.query_params,
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request)
        product_service.log_offer_page_loaded(
            request.user,
            total_count=paginator.page.paginator.count,
            page_size=len(page),
        )
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ProductOffersView(APIView):
    serializer_class = BuyerOfferSerializer

    @product_offers_schema
    ## 2.3. Список предложений товара ----
    def get(self, request: Request, pk: int):
        queryset = product_service.get_available_offers(
            request.user,
            request.query_params,
            product_id=pk,
        )
        paginator = DefaultPagination()
        page = paginator.paginate_queryset(queryset, request)
        product_service.log_offer_page_loaded(
            request.user,
            product_id=pk,
            total_count=paginator.page.paginator.count,
            page_size=len(page),
        )
        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class OfferDetailView(APIView):
    serializer_class = BuyerOfferSerializer

    @offer_detail_schema
    ## 2.4. Карточка предложения ----
    def get(self, _: Request, pk: int):
        offer = product_service.get_offer(pk)
        serializer = self.serializer_class(offer)
        return Response(serializer.data, status=status.HTTP_200_OK)


# 3. Корзина ----
class BasketView(APIView):
    """
    Взаимодействие с корзиной
    """

    permission_classes = [IsBuyer]
    serializer_class = BasketSerializer

    @basket_retrieve_schema
    ## 3.1. Получить корзину ----
    def get(self, request: Request):
        serializer = self.serializer_class(
            basket_service.get_basket_summary(request.user)
        )
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    ## 3.3. Очистить корзину ----
    @basket_clear_schema
    def delete(self, request: Request):
        basket_service.clear_basket(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BasketItemsView(APIView):
    permission_classes = [IsBuyer]
    serializer_class = AddToBasketSerializer

    ## 3.4. Добавить позицию корзины ----
    @basket_item_add_schema
    def post(self, request: Request):
        serializer = AddToBasketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_item = basket_service.add_basket_item(
            request.user,
            product_info_id=serializer.validated_data["offer_id"],
            quantity=serializer.validated_data["quantity"],
        )
        response_serializer = BasketItemSummarySerializer(
            basket_service.build_basket_item_payload(order_item)
        )
        return Response(
            {"data": response_serializer.data},
            status=status.HTTP_201_CREATED,
        )


class BasketItemDetailView(APIView):
    permission_classes = [IsBuyer]
    serializer_class = UpdateBasketItemSerializer

    ## 3.5. Изменить позицию корзины ----
    @basket_item_update_schema
    def patch(self, request: Request, pk: int):
        serializer = UpdateBasketItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_item = basket_service.update_basket_item_quantity(
            request.user,
            item_id=pk,
            quantity=serializer.validated_data["quantity"],
        )
        response_serializer = BasketItemSummarySerializer(
            basket_service.build_basket_item_payload(order_item)
        )
        return Response(
            {"data": response_serializer.data},
            status=status.HTTP_200_OK,
        )

    ## 3.6. Удалить позицию корзины ----
    @basket_item_delete_schema
    def delete(self, request: Request, pk: int):
        basket_service.delete_basket_item(request.user, item_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


# 4. Взаимодействие с адресом доставки ----
class ContactView(APIView):
    """
    Взаимодействие с адресом доставки
    """

    permission_classes = [IsBuyer]
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
            status=status.HTTP_200_OK,
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
            status=status.HTTP_201_CREATED,
        )


class ContactDetailView(APIView):
    permission_classes = [IsBuyer]
    serializer_class = ContactSerializer

    ## 4.4. Получить адрес доставки ----
    @contact_detail_schema
    def get(self, request: Request, pk: int):
        contact = contact_service.get_user_contact(request.user, pk)
        serializer = self.serializer_class(contact)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    ## 4.5. Обновить адрес доставки ----
    @contact_update_schema
    def patch(self, request: Request, pk: int):
        serializer = self.serializer_class(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        contact = contact_service.update_contact(
            request.user,
            pk,
            serializer.validated_data,
        )
        return Response(self.serializer_class(contact).data, status=status.HTTP_200_OK)

    ## 4.6. Удалить адрес доставки ----
    @contact_delete_schema
    def delete(self, request: Request, pk: int):
        contact_service.delete_contact(request.user, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


# 5. Подтверждение заказа (изменение его статуса) ----
class OrderConfirmView(APIView):
    """
    Подтверждение заказа
    """

    permission_classes = [IsBuyer]
    throttle_classes = [ConfirmOrderRateThrottle]

    @order_confirm_schema
    ## 5.1. Подтвердить заказ ----
    def post(self, request: Request):
        serializer = OrderConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = order_service.confirm_order(
            request.user,
            order_id=serializer.validated_data["order_id"],
            contact_id=serializer.validated_data["contact_id"],
        )

        response_serializer = OrderDetailSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


# 6. Список заказов (история заказов) ----
class OrderListView(APIView):
    """
    История заказов
    """

    permission_classes = [IsBuyer]

    @order_history_schema
    ## 6.1. Получить историю заказов ----
    def get(self, request: Request):
        pagination = DefaultPagination()
        orders = order_service.get_order_history(request.user)
        queryset = pagination.paginate_queryset(queryset=orders, request=request)
        serializer = OrderHistorySerializer(queryset, many=True)
        return pagination.get_paginated_response(serializer.data)


# 7. Детальная информация о заказе ----
class OrderDetailView(APIView):
    permission_classes = [IsBuyer]
    serializer_class = OrderDetailSerializer

    @order_retrieve_schema
    ## 7.1. Получить заказ ----
    def get(self, request: Request, pk):
        order = order_service.get_user_order(request.user, pk)
        serializer = self.serializer_class(order)
        return Response(serializer.data)


# 7.3. Отменить заказ покупателем ----
class OrderCancelView(APIView):
    permission_classes = [IsBuyer]
    serializer_class = OrderDetailSerializer

    @order_cancel_schema
    def post(self, request: Request, pk: int):
        order = order_service.get_user_order(request.user, pk)
        order = order_service.cancel_order_by_buyer(order)
        serializer = self.serializer_class(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


# 8. Администрирование ----
class AdminUserListView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_user_list_schema
    ## 8.1. Получить пользователей ----
    def get(self, request: Request):
        search = request.query_params.get("search")
        pagination = DefaultPagination()
        page = pagination.paginate_queryset(
            admin_service.get_all_users(search=search), request
        )
        serializer = UserSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)


class AdminUserDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_user_update_schema
    ## 8.2. Обновить пользователя ----
    def patch(self, request: Request, pk: int):
        user = admin_service.get_user(pk)
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = admin_service.update_user(pk, serializer.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class AdminShopListView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_shop_list_schema
    ## 8.3. Получить магазины ----
    def get(self, request: Request):
        search = request.query_params.get("search")
        pagination = DefaultPagination()
        page = pagination.paginate_queryset(
            shop_service.get_all_shops(search=search), request
        )
        serializer = ShopSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)


class AdminShopDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_shop_update_schema
    ## 8.4. Обновить магазин ----
    def patch(self, request: Request, pk: int):
        serializer = AdminShopUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        shop = admin_service.update_shop(pk, serializer.validated_data)
        return Response(ShopSerializer(shop).data, status=status.HTTP_200_OK)


class AdminCategoryListCreateView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_category_list_schema
    ## 8.5. Получить категории ----
    def get(self, request: Request):
        search = request.query_params.get("search")
        pagination = DefaultPagination()
        page = pagination.paginate_queryset(
            admin_service.get_all_categories(search=search), request
        )
        serializer = CategorySerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    @admin_category_create_schema
    ## 8.6. Создать категорию ----
    def post(self, request: Request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = admin_service.create_category(serializer.validated_data)
        return Response(
            CategorySerializer(category).data, status=status.HTTP_201_CREATED
        )


class AdminCategoryDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_category_update_schema
    ## 8.7. Обновить категорию ----
    def patch(self, request: Request, pk: int):
        serializer = CategorySerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = admin_service.update_category(pk, serializer.validated_data)
        return Response(CategorySerializer(category).data, status=status.HTTP_200_OK)


class AdminProductListCreateView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_product_list_schema
    ## 8.8. Получить товары ----
    def get(self, request: Request):
        search = request.query_params.get("search")
        pagination = DefaultPagination()
        page = pagination.paginate_queryset(
            admin_service.get_all_products(search=search), request
        )
        serializer = ProductSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    @admin_product_create_schema
    ## 8.9. Создать товар ----
    def post(self, request: Request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = admin_service.create_product(serializer.validated_data)
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_product_update_schema
    ## 8.10. Обновить товар ----
    def patch(self, request: Request, pk: int):
        serializer = ProductSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = admin_service.update_product(pk, serializer.validated_data)
        return Response(ProductSerializer(product).data, status=status.HTTP_200_OK)


class AdminParameterListCreateView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_parameter_list_schema
    ## 8.11. Получить параметры ----
    def get(self, request: Request):
        search = request.query_params.get("search")
        pagination = DefaultPagination()
        page = pagination.paginate_queryset(
            admin_service.get_all_parameters(search=search), request
        )
        serializer = ParameterSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)

    @admin_parameter_create_schema
    ## 8.12. Создать параметр ----
    def post(self, request: Request):
        serializer = ParameterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parameter = admin_service.create_parameter(serializer.validated_data)
        return Response(
            ParameterSerializer(parameter).data, status=status.HTTP_201_CREATED
        )


class AdminParameterDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_parameter_update_schema
    ## 8.13. Обновить параметр ----
    def patch(self, request: Request, pk: int):
        serializer = ParameterSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        parameter = admin_service.update_parameter(pk, serializer.validated_data)
        return Response(ParameterSerializer(parameter).data, status=status.HTTP_200_OK)


class AdminOfferListView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_offer_list_schema
    ## 8.14. Получить предложения ----
    def get(self, request: Request):
        search = request.query_params.get("search")
        pagination = DefaultPagination()
        page = pagination.paginate_queryset(
            shop_service.get_all_offers(search=search), request
        )
        serializer = OfferSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)


class AdminOfferDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_offer_update_schema
    ## 8.15. Обновить предложение ----
    def patch(self, request: Request, pk: int):
        serializer = AdminOfferUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        offer = admin_service.update_offer(pk, serializer.validated_data)
        return Response(OfferSerializer(offer).data, status=status.HTTP_200_OK)


class AdminOrderListView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_order_list_schema
    ## 8.16. Получить заказы (с фильтрацией по статусу) ----
    def get(self, request: Request):
        search = request.query_params.get("search")
        status = request.query_params.get("status")
        pagination = DefaultPagination()
        page = pagination.paginate_queryset(
            order_service.get_all_orders(search=search, status=status), request
        )
        serializer = OrderDetailSerializer(page, many=True)
        return pagination.get_paginated_response(serializer.data)


class AdminOrderDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_order_update_schema
    ## 8.17. Обновить заказ ----
    def patch(self, request: Request, pk: int):
        order = order_service.get_admin_order(pk)
        serializer = AdminOrderUpdateSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        order = order_service.update_order_state_by_admin(
            request.user,
            order,
            new_state=serializer.validated_data.get("state"),
            cancellation_reason=serializer.validated_data.get(
                "cancellation_reason", ""
            ),
        )
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_200_OK)


class AdminOrderItemDetailView(APIView):
    permission_classes = [IsAdminUserType]

    @admin_order_item_update_schema
    ## 8.18. Обновить позицию заказа ----
    def patch(self, request: Request, pk: int):
        serializer = AdminOrderItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = order_service.update_order_item_state_by_admin(
            request.user,
            item_id=pk,
            new_state=serializer.validated_data["state"],
        )
        return Response(OrderItemSerializer(item).data, status=status.HTTP_200_OK)
