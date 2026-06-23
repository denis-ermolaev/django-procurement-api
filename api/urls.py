from django.urls import path

from api.views import (
    AdminCategoryDetailView,
    AdminCategoryListCreateView,
    AdminOfferDetailView,
    AdminOfferListView,
    AdminOrderDetailView,
    AdminOrderItemDetailView,
    AdminOrderListView,
    AdminParameterDetailView,
    AdminParameterListCreateView,
    AdminProductDetailView,
    AdminProductListCreateView,
    AdminShopApproveView,
    AdminShopBlockView,
    AdminShopDetailView,
    AdminShopListView,
    AdminUserDetailView,
    AdminUserListView,
    BasketItemDetailView,
    BasketItemsView,
    BasketView,
    ContactDetailView,
    ContactView,
    LegacyContactView,
    OfferDetailView,
    OfferListView,
    OrderConfirmView,
    OrderDetailView,
    OrderListView,
    ProductDetailView,
    ProductListView,
    ProductOffersView,
    ShopImportView,
    ShopOfferDetailView,
    ShopOfferListCreateView,
    ShopOrderItemDetailView,
    ShopOrderItemListView,
    ShopProfileView,
    ShopRegistrationView,
)

# 1. Маршруты API ----
urlpatterns = [
    ## 1.1. Магазины ----
    path("shops/register/", ShopRegistrationView.as_view(), name="shop-register"),
    path("shop/profile/", ShopProfileView.as_view(), name="shop-profile"),
    path("shop/imports/", ShopImportView.as_view(), name="shop-imports"),
    path("shop/offers/", ShopOfferListCreateView.as_view(), name="shop-offers"),
    path(
        "shop/offers/<int:pk>/",
        ShopOfferDetailView.as_view(),
        name="shop-offer-detail",
    ),
    path(
        "shop/order-items/",
        ShopOrderItemListView.as_view(),
        name="shop-order-items",
    ),
    path(
        "shop/order-items/<int:pk>/",
        ShopOrderItemDetailView.as_view(),
        name="shop-order-item-detail",
    ),
    ## 1.2. Администрирование ----
    path("admin/users/", AdminUserListView.as_view(), name="admin-users"),
    path(
        "admin/users/<int:pk>/",
        AdminUserDetailView.as_view(),
        name="admin-user-detail",
    ),
    path("admin/shops/", AdminShopListView.as_view(), name="admin-shops"),
    path(
        "admin/shops/<int:pk>/",
        AdminShopDetailView.as_view(),
        name="admin-shop-detail",
    ),
    path(
        "admin/shops/<int:pk>/approve/",
        AdminShopApproveView.as_view(),
        name="admin-shop-approve",
    ),
    path(
        "admin/shops/<int:pk>/block/",
        AdminShopBlockView.as_view(),
        name="admin-shop-block",
    ),
    path(
        "admin/categories/",
        AdminCategoryListCreateView.as_view(),
        name="admin-categories",
    ),
    path(
        "admin/categories/<int:pk>/",
        AdminCategoryDetailView.as_view(),
        name="admin-category-detail",
    ),
    path(
        "admin/products/", AdminProductListCreateView.as_view(), name="admin-products"
    ),
    path(
        "admin/products/<int:pk>/",
        AdminProductDetailView.as_view(),
        name="admin-product-detail",
    ),
    path(
        "admin/parameters/",
        AdminParameterListCreateView.as_view(),
        name="admin-parameters",
    ),
    path(
        "admin/parameters/<int:pk>/",
        AdminParameterDetailView.as_view(),
        name="admin-parameter-detail",
    ),
    path("admin/offers/", AdminOfferListView.as_view(), name="admin-offers"),
    path(
        "admin/offers/<int:pk>/",
        AdminOfferDetailView.as_view(),
        name="admin-offer-detail",
    ),
    path("admin/orders/", AdminOrderListView.as_view(), name="admin-orders"),
    path(
        "admin/orders/<int:pk>/",
        AdminOrderDetailView.as_view(),
        name="admin-order-detail",
    ),
    path(
        "admin/order-items/<int:pk>/",
        AdminOrderItemDetailView.as_view(),
        name="admin-order-item-detail",
    ),
    ## 1.3. Каталог ----
    path("offers/<int:pk>/", OfferDetailView.as_view(), name="offer-detail"),
    path("offers/", OfferListView.as_view(), name="offers"),
    path(
        "products/<int:pk>/offers/",
        ProductOffersView.as_view(),
        name="product-offers",
    ),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("products/", ProductListView.as_view(), name="products"),
    ## 1.4. Корзина и контакты ----
    path(
        "basket/items/<int:pk>/",
        BasketItemDetailView.as_view(),
        name="basket-item-detail",
    ),
    path("basket/items/", BasketItemsView.as_view(), name="basket-items"),
    path("basket/", BasketView.as_view(), name="basket"),
    path("contacts/<int:pk>/", ContactDetailView.as_view(), name="contact-detail"),
    path("contacts/", ContactView.as_view(), name="contacts"),
    path("contact/", LegacyContactView.as_view(), name="contact"),
    ## 1.5. Заказы ----
    path("order/confirm/", OrderConfirmView.as_view(), name="order-confirm"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/", OrderListView.as_view(), name="orders"),
]
