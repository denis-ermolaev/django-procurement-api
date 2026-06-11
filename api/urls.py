from django.urls import path

from api.views import CheckView

urlpatterns = [
    path("check/", CheckView.as_view(), name="registration"),
]
