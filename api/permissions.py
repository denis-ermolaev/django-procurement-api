from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from api.models import Shop


# 1. Ролевые permissions ----
class IsBuyer(BasePermission):
    message = "Доступ разрешен только покупателям."

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.type == "buyer")


class IsShop(BasePermission):
    message = "Доступ разрешен только пользователям магазинов."

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.type == "shop")


class IsActiveShop(BasePermission):
    message = "Доступ разрешен только активным магазинам."

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.type == "shop"):
            return False

        return Shop.objects.filter(owner=user, status="active").exists()


class IsAdminUserType(BasePermission):
    message = "Доступ разрешен только администраторам."

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_staff and user.type == "admin"
        )
