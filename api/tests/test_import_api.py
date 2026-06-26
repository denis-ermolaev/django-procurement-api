"""Тесты API импорта YAML-прайсов."""

from io import BytesIO
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from api.models import ImportJob, Shop, User
from api.tests.base import APITestCase


class ShopImportAPITests(APITestCase):
    """Проверка эндпоинтов импорта прайсов."""

    def setUp(self) -> None:
        super().setUp()
        # Создаём пользователя-магазин с активным магазином
        self.shop_user = User.objects.create_user(
            email="import-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.import_shop = Shop.objects.create(
            owner=self.shop_user,
            name="Import shop",
            url="https://import.test",
            status="active",
        )

    def test_import_requires_authentication(self) -> None:
        """POST /api/shop/imports/ без аутентификации — 401."""
        response = self.api_client.post(reverse("shop-imports"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_import_requires_active_shop(self) -> None:
        """POST /api/shop/imports/ для pending магазина — 403."""
        self.import_shop.status = "pending"
        self.import_shop.save(update_fields=["status"])
        self.api_client.force_authenticate(user=self.shop_user)

        response = self.api_client.post(
            reverse("shop-imports"), {"content": "shop: Test"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_import_requires_buyer_role(self) -> None:
        """POST /api/shop/imports/ для покупателя — 403."""
        self.authenticate()
        response = self.api_client.post(
            reverse("shop-imports"), {"content": "shop: Test"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("api.views.shop_data_service.import_shop_data_async")
    def test_import_accepts_content_and_returns_202(self, mock_import) -> None:
        """POST /api/shop/imports/ с content — 202."""
        self.api_client.force_authenticate(user=self.shop_user)

        response = self.api_client.post(
            reverse("shop-imports"),
            {
                "content": (
                    "shop: Test Shop\n"
                    "categories:\n"
                    "  - id: 1\n"
                    "    name: Cat\n"
                    "goods:\n"
                    "  - id: p1\n"
                    "    category: 1\n"
                    "    name: Prod\n"
                    "    price: 100\n"
                    "    price_rrc: 120\n"
                    "    quantity: 10"
                )
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("job_id", response.data)
        self.assertEqual(response.data["status"], "processing")
        mock_import.delay.assert_called_once()

    @patch("api.views.shop_data_service.import_shop_data_async")
    def test_import_accepts_file_and_returns_202(self, mock_import) -> None:
        """POST /api/shop/imports/ с файлом — 202."""
        self.api_client.force_authenticate(user=self.shop_user)

        file_content = (
            b"shop: File Shop\n"
            b"categories:\n"
            b"  - id: 1\n"
            b"    name: Cat\n"
            b"goods:\n"
            b"  - id: p1\n"
            b"    category: 1\n"
            b"    name: Prod\n"
            b"    price: 100\n"
            b"    price_rrc: 120\n"
            b"    quantity: 10"
        )
        response = self.api_client.post(
            reverse("shop-imports"),
            {"file": BytesIO(file_content)},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("job_id", response.data)
        mock_import.delay.assert_called_once()

    def test_import_rejects_no_content_and_no_file(self) -> None:
        """POST /api/shop/imports/ без file и content — 400."""
        self.api_client.force_authenticate(user=self.shop_user)

        response = self.api_client.post(reverse("shop-imports"), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_import_status_requires_authentication(self) -> None:
        """GET /api/shop/imports/{id}/status/ без аутентификации — 401."""
        response = self.api_client.get(reverse("shop-import-status", args=[1]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_import_status_returns_job_info(self) -> None:
        """GET /api/shop/imports/{id}/status/ для существующей задачи."""
        self.api_client.force_authenticate(user=self.shop_user)
        job = ImportJob.objects.create(shop=self.import_shop, status="completed")

        response = self.api_client.get(reverse("shop-import-status", args=[job.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["id"], job.pk)
        self.assertIn("error_log", response.data)
        self.assertIn("stats", response.data)

    def test_import_status_hides_error_log_for_success(self) -> None:
        """GET /api/shop/imports/{id}/status/ — error_log пуст для успешных."""
        self.api_client.force_authenticate(user=self.shop_user)
        job = ImportJob.objects.create(
            shop=self.import_shop,
            status="completed",
            error_log="hidden error",
        )

        response = self.api_client.get(reverse("shop-import-status", args=[job.pk]))

        self.assertEqual(response.data["error_log"], "")

    def test_import_status_shows_error_log_for_failed(self) -> None:
        """GET /api/shop/imports/{id}/status/ — error_log виден при failed."""
        self.api_client.force_authenticate(user=self.shop_user)
        job = ImportJob.objects.create(
            shop=self.import_shop,
            status="failed",
            error_log="traceback details",
        )

        response = self.api_client.get(reverse("shop-import-status", args=[job.pk]))

        self.assertEqual(response.data["error_log"], "traceback details")

    def test_import_status_checks_ownership(self) -> None:
        """GET /api/shop/imports/{id}/status/ для чужой задачи — 404."""
        other_shop_user = User.objects.create_user(
            email="other-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        other_shop = Shop.objects.create(
            owner=other_shop_user,
            name="Other shop",
            status="active",
        )
        other_job = ImportJob.objects.create(shop=other_shop, status="processing")

        self.api_client.force_authenticate(user=self.shop_user)

        response = self.api_client.get(
            reverse("shop-import-status", args=[other_job.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_import_status_returns_404_for_missing_job(self) -> None:
        """GET /api/shop/imports/{id}/status/ для несуществующей — 404."""
        self.api_client.force_authenticate(user=self.shop_user)

        response = self.api_client.get(reverse("shop-import-status", args=[999_999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
