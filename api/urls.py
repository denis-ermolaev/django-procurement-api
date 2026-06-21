from django.urls import path

from api.views import (
    BasketView,
    ContactView,
    OrderConfirmView,
    OrderDetailView,
    OrderListView,
    ProductDetailView,
    ProductListView,
)

# 1. Маршруты API ----
urlpatterns = [
    ## 1.1. Каталог ----
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("products/", ProductListView.as_view(), name="products"),
    ## 1.2. Корзина и контакты ----
    path("basket/", BasketView.as_view(), name="basket"),
    path("contact/", ContactView.as_view(), name="contact"),
    ## 1.3. Заказы ----
    path("order/confirm/", OrderConfirmView.as_view(), name="order-confirm"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/", OrderListView.as_view(), name="orders"),
]
