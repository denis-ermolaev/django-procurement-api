import logging
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework import status

from api.management.email_service import send_order_confirmation
from api.middleware import RequestLogMiddleware
from api.models import Order
from api.tests.base import APITestCase


class RequestLoggingAPITests(APITestCase):
    def test_request_logging_records_successful_request(self) -> None:
        self.authenticate()

        with self.assertLogs("api.request", level="INFO") as captured:
            response = self.api_client.get(reverse("products"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(
                "request_completed method=GET path=/api/products/ status_code=200"
                in message
                for message in captured.output
            )
        )

    def test_request_logging_records_client_error_as_warning(self) -> None:
        with self.assertLogs("api.request", level="WARNING") as captured:
            response = self.api_client.get(reverse("products"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(
            any(
                "request_completed method=GET path=/api/products/ status_code=401"
                in message
                for message in captured.output
            )
        )

    def test_basket_add_records_business_logs(self) -> None:
        self.authenticate()

        with self.assertLogs("api.services.basket", level="INFO") as captured:
            response = self.api_client.post(
                reverse("basket"),
                {"product_info_id": self.product_info.pk, "quantity": 2},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any("basket_created user_id=" in message for message in captured.output)
        )
        self.assertTrue(
            any(
                "basket_item_created user_id=" in message for message in captured.output
            )
        )


class BusinessLoggingTests(APITestCase):
    @override_settings(ADMIN_EMAILS=["admin@example.com"])
    def test_order_confirmation_email_records_business_logs(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")

        with self.assertLogs("api.management.email_service", level="INFO") as captured:
            send_order_confirmation(order)

        self.assertTrue(
            any(
                "order_customer_email_sent order_id=" in message
                for message in captured.output
            )
        )
        self.assertTrue(
            any(
                "order_admin_email_sent order_id=" in message
                for message in captured.output
            )
        )

    def test_load_shop_data_records_import_summary_logs(self) -> None:
        yaml_data = """
shop: Log test shop
categories:
  - id: 1
    name: Phones
goods:
  - id: 100
    category: 1
    name: Logged Phone
    price: 100
    price_rrc: 120
    quantity: 5
    parameters:
      color: black
"""
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "shop.yaml"
            yaml_path.write_text(yaml_data, encoding="utf-8")

            with self.assertLogs("api.services.shop_data", level="INFO") as captured:
                call_command("load_shop_data", str(yaml_path), stdout=StringIO())

        self.assertTrue(
            any("shop_data_load_started" in message for message in captured.output)
        )
        self.assertTrue(
            any(
                "shop_data_load_completed" in message and "loaded_count=1" in message
                for message in captured.output
            )
        )


class RequestLogMiddlewareUnitTests(TestCase):
    def test_request_logging_records_exception(self) -> None:
        request = RequestFactory().get("/broken/")

        def get_response(_):
            raise RuntimeError("boom")

        middleware = RequestLogMiddleware(get_response)

        with self.assertLogs("api.request", level="ERROR") as captured:
            with self.assertRaisesMessage(RuntimeError, "boom"):
                middleware(request)

        self.assertTrue(
            any(
                "request_failed method=GET path=/broken/" in message
                for message in captured.output
            )
        )

    def test_response_log_level_depends_on_status_code(self) -> None:
        self.assertEqual(
            RequestLogMiddleware.get_response_log_level(status.HTTP_200_OK),
            logging.INFO,
        )
        self.assertEqual(
            RequestLogMiddleware.get_response_log_level(status.HTTP_404_NOT_FOUND),
            logging.WARNING,
        )
        self.assertEqual(
            RequestLogMiddleware.get_response_log_level(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            logging.ERROR,
        )
