from django.urls import path

from api.views import (
    BasketView,
    ContactView,
    OrderConfirmView,
    OrderHistoryView,
    ProductListView,
)

urlpatterns = [
    path("products/", ProductListView.as_view(), name="products"),
    path("basket/", BasketView.as_view(), name="basket"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("order/confirm/", OrderConfirmView.as_view(), name="order-confirm"),
    path("orders/history/", OrderHistoryView.as_view(), name="order-history"),
]
