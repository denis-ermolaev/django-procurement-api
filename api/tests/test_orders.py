from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from api.models import Contact, Order, OrderItem, User
from api.services.email_service import (
    send_order_confirmation,
)
from api.tests.base import APITestCase


class OrderAPITests(APITestCase):
    contact_payload = {
        "city": "Kaliningrad",
        "street": "Lenina",
        "house": "1",
        "phone": "+70000000000",
    }

    def test_confirm_order_changes_state_and_sends_notification(self) -> None:
        contact = Contact.objects.create(user=self.user, **self.contact_payload)
        order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2
        )
        self.authenticate()

        with (
            patch("api.services.orders.send_order_confirmation_async") as send_async,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order.pk, "contact_id": contact.pk},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        order_item = OrderItem.objects.get(order=order)
        self.product_info.refresh_from_db()
        self.assertEqual(order.state, "confirmed")
        self.assertEqual(order.contact, contact)
        self.assertIsNotNone(order.confirmed_at)
        self.assertEqual(order_item.state, "confirmed")
        self.assertEqual(order_item.unit_price, 100)
        self.assertEqual(order_item.price_rrc_snapshot, 120)
        self.assertEqual(order_item.product_name_snapshot, self.product.name)
        self.assertEqual(order_item.offer_name_snapshot, self.product_info.name)
        self.assertEqual(order_item.shop_name_snapshot, self.shop.name)
        self.assertEqual(self.product_info.reserved_quantity, 2)
        self.assertEqual(response.data["id"], order.pk)
        self.assertEqual(response.data["total_sum"], 200)
        send_async.delay.assert_called_once_with(order.pk)

    def test_confirm_order_keeps_price_snapshot_after_offer_price_change(self) -> None:
        contact = Contact.objects.create(user=self.user, **self.contact_payload)
        order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2
        )
        self.authenticate()

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order.pk, "contact_id": contact.pk},
                format="json",
            )
        self.product_info.price = 999
        self.product_info.save(update_fields=["price"])

        history_response = self.api_client.get(reverse("orders"))
        detail_response = self.api_client.get(reverse("order-detail", args=[order.pk]))

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.data["results"][0]["total_sum"], 200)
        self.assertEqual(detail_response.data["total_sum"], 200)
        self.assertEqual(detail_response.data["items"][0]["unit_price"], 100)

    def test_confirm_order_rejects_another_users_order_or_contact(self) -> None:
        own_contact = Contact.objects.create(user=self.user, **self.contact_payload)
        other_contact = Contact.objects.create(
            user=self.other_user, **self.contact_payload
        )
        other_order = Order.objects.create(user=self.other_user, state="basket")
        own_order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=own_order, product_info=self.product_info, quantity=1
        )
        self.authenticate()

        responses = (
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": other_order.pk, "contact_id": own_contact.pk},
                format="json",
            ),
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": own_order.pk, "contact_id": other_contact.pk},
                format="json",
            ),
        )

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_confirm_order_rejects_empty_basket(self) -> None:
        contact = Contact.objects.create(user=self.user, **self.contact_payload)
        order = Order.objects.create(user=self.user, state="basket")
        self.authenticate()

        response = self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order.pk, "contact_id": contact.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.state, "basket")

    def test_order_history_excludes_basket_and_calculates_total(self) -> None:
        Order.objects.create(user=self.user, state="basket")
        order = Order.objects.create(user=self.user, state="confirmed")
        OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=3
        )
        Order.objects.create(user=self.other_user, state="confirmed")
        self.authenticate()

        response = self.api_client.get(reverse("orders"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], order.pk)
        self.assertEqual(response.data["results"][0]["total_sum"], 300)

    def test_order_detail_is_available_only_to_owner(self) -> None:
        own_order = Order.objects.create(user=self.user, state="confirmed")
        own_item = OrderItem.objects.create(
            order=own_order, product_info=self.product_info, quantity=2
        )
        other_order = Order.objects.create(user=self.other_user, state="confirmed")
        self.authenticate()

        response = self.api_client.get(reverse("order-detail", args=[own_order.pk]))
        forbidden_response = self.api_client.get(
            reverse("order-detail", args=[other_order.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], own_order.pk)
        self.assertEqual(response.data["total_sum"], 200)
        self.assertEqual(response.data["items"][0]["id"], own_item.pk)
        self.assertEqual(
            response.data["items"][0]["product_info"], self.product_info.pk
        )
        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_order_cancel_via_dedicated_endpoint(self) -> None:
        own_order = Order.objects.create(user=self.user, state="confirmed")
        own_item = OrderItem.objects.create(
            order=own_order,
            product_info=self.product_info,
            quantity=1,
            state="confirmed",
        )
        other_order = Order.objects.create(user=self.other_user, state="confirmed")
        self.authenticate()

        # POST /orders/{id}/cancel/ — корректная отмена
        response = self.api_client.post(
            reverse("order-cancel", args=[own_order.pk]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["id"], own_item.pk)
        own_order.refresh_from_db()
        own_item.refresh_from_db()
        self.assertEqual(own_order.state, "canceled")
        self.assertEqual(own_item.state, "canceled")

        # POST /orders/{id}/cancel/ — чужой заказ
        forbidden_response = self.api_client.post(
            reverse("order-cancel", args=[other_order.pk]),
            format="json",
        )
        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_buyer_can_cancel_partially_canceled_order_before_processing(self) -> None:
        order = Order.objects.create(user=self.user, state="partially_canceled")
        canceled_item = OrderItem.objects.create(
            order=order,
            product_info=self.other_product_info,
            quantity=1,
            state="canceled",
        )
        confirmed_item = OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=2,
            state="confirmed",
        )
        self.product_info.reserved_quantity = 2
        self.product_info.save(update_fields=["reserved_quantity"])
        self.authenticate()

        response = self.api_client.post(
            reverse("order-cancel", args=[order.pk]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        canceled_item.refresh_from_db()
        confirmed_item.refresh_from_db()
        self.product_info.refresh_from_db()
        self.assertEqual(order.state, "canceled")
        self.assertEqual(canceled_item.state, "canceled")
        self.assertEqual(confirmed_item.state, "canceled")
        self.assertEqual(self.product_info.reserved_quantity, 0)

    def test_admin_cannot_cancel_order_with_sent_item(self) -> None:
        admin_user = User.objects.create_user(
            email="order-admin@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        order = Order.objects.create(user=self.user, state="sent")
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=1,
            state="sent",
        )
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.patch(
            reverse("admin-order-detail", args=[order.pk]),
            {"state": "canceled", "cancellation_reason": "Ошибка доставки"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.state, "sent")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ADMIN_EMAILS=["admin@example.com"],
    )
    def test_order_confirmation_email_is_sent_to_customer_and_admin(self) -> None:
        contact = Contact.objects.create(user=self.user, **self.contact_payload)
        order = Order.objects.create(user=self.user, state="confirmed", contact=contact)

        send_order_confirmation(order)

        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertEqual(mail.outbox[1].to, ["admin@example.com"])
        self.assertIn(f"Заказ #{order.pk}", mail.outbox[0].subject)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ADMIN_EMAILS=[],
    )
    def test_order_confirmation_email_skips_admins_when_not_configured(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")

        send_order_confirmation(order)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        ADMIN_EMAILS=["admin@example.com"],
    )
    def test_order_confirmation_email_skips_customer_without_email(self) -> None:
        self.user.email = ""
        self.user.save(update_fields=["email"])
        order = Order.objects.create(user=self.user, state="confirmed")

        send_order_confirmation(order)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertIn("Email клиента: None", mail.outbox[0].body)


class OrderCancelAPITests(APITestCase):
    def test_cancel_order_requires_authentication(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")

        response = self.api_client.post(
            reverse("order-cancel", args=[order.pk]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cancel_order_happy_path(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2, state="confirmed"
        )
        self.product_info.reserved_quantity = 2
        self.product_info.save(update_fields=["reserved_quantity"])
        self.authenticate()

        response = self.api_client.post(
            reverse("order-cancel", args=[order.pk]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.state, "canceled")

    def test_cancel_order_fails_if_already_shipped(self) -> None:
        order = Order.objects.create(user=self.user, state="sent")
        self.authenticate()

        response = self.api_client.post(
            reverse("order-cancel", args=[order.pk]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_order_fails_from_other_user(self) -> None:
        order = Order.objects.create(user=self.other_user, state="confirmed")
        self.authenticate()

        response = self.api_client.post(
            reverse("order-cancel", args=[order.pk]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_order_releases_reserved_stock(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2, state="confirmed"
        )
        self.product_info.reserved_quantity = 2
        self.product_info.save(update_fields=["reserved_quantity"])
        self.authenticate()

        response = self.api_client.post(
            reverse("order-cancel", args=[order.pk]), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 0)
