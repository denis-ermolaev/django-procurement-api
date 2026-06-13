from django.urls import path

from api.views import (
    BasketView,
    CheckView,
    ContactView,
    OrderConfirmView,
    OrderHistoryView,
    ProductListView,
)

urlpatterns = [
    path("check/", CheckView.as_view(), name="check"),
    path("products/", ProductListView.as_view(), name="products"),
    path("basket/", BasketView.as_view(), name="basket"),
    path("contact/", ContactView.as_view(), name="contact"),
    path("order/confirm/", OrderConfirmView.as_view(), name="order-confirm"),
    path("orders/history/", OrderHistoryView.as_view(), name="order-history"),
]
