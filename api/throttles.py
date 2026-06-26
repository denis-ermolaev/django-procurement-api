"""Кастомные throttle классы для rate limiting чувствительных endpoints."""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class ShopRegisterRateThrottle(AnonRateThrottle):
    """Ограничение регистрации магазинов: 5 запросов в минуту."""

    scope = "shop_register"


class ImportRateThrottle(UserRateThrottle):
    """Ограничение импорта прайсов: 10 запросов в минуту."""

    scope = "shop_import"


class ConfirmOrderRateThrottle(UserRateThrottle):
    """Ограничение подтверждения заказов: 10 запросов в минуту."""

    scope = "order_confirm"
