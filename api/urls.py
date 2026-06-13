from django.urls import path

from api.views import BasketView, CheckView, ContactView, ProductListView

urlpatterns = [
    path("check/", CheckView.as_view(), name="registration"),
    path("products/", ProductListView.as_view(), name="registration"),
    path("basket/", BasketView.as_view(), name="registration"),
    path("contact/", ContactView.as_view(), name="registration"),
]
