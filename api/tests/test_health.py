"""Тесты health-check endpoint."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.tests.base import APITestCase


class HealthCheckTests(APITestCase):
    """Проверка health-check."""

    def test_health_check_returns_200_without_auth(self) -> None:
        """GET /health/ доступен без аутентификации."""
        client = APIClient()
        response = client.get(reverse("health-check"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok", "db": "connected"})

    def test_health_check_works_for_authenticated_users(self) -> None:
        """GET /health/ работает и для аутентифицированных пользователей."""
        self.authenticate()
        response = self.api_client.get(reverse("health-check"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["db"], "connected")
