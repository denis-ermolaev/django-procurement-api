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

urlpatterns = [
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product-detail"),
    path("products/", ProductListView.as_view(), name="products"),
    path("basket/", BasketView.as_view(), name="basket"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("order/confirm/", OrderConfirmView.as_view(), name="order-confirm"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("orders/", OrderListView.as_view(), name="orders"),
]
