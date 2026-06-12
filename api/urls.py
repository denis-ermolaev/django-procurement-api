from django.urls import path

from api.views import CheckView, ProductListView

urlpatterns = [
    path("check/", CheckView.as_view(), name="registration"),
    path("products/", ProductListView.as_view(), name="registration"),
]
