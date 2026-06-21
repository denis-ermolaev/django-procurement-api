from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from api.management.email_service import send_order_confirmation
from api.models import Contact, Order, OrderItem
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

        with patch("api.views.send_order_confirmation") as send_confirmation:
            response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order.pk, "contact_id": contact.pk},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.state, "confirmed")
        self.assertEqual(order.contact, contact)
        send_confirmation.assert_called_once_with(order)

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
        other_order = Order.objects.create(user=self.other_user, state="confirmed")
        self.authenticate()

        response = self.api_client.get(reverse("order-detail", args=[own_order.pk]))
        forbidden_response = self.api_client.get(
            reverse("order-detail", args=[other_order.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], own_order.pk)
        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_order_patch_validates_state_and_checks_ownership(self) -> None:
        own_order = Order.objects.create(user=self.user, state="confirmed")
        other_order = Order.objects.create(user=self.other_user, state="confirmed")
        self.authenticate()

        invalid_response = self.api_client.patch(
            reverse("order-detail", args=[own_order.pk]),
            {"state": "delivered"},
            format="json",
        )
        forbidden_response = self.api_client.patch(
            reverse("order-detail", args=[other_order.pk]),
            {"state": "new"},
            format="json",
        )
        response = self.api_client.patch(
            reverse("order-detail", args=[own_order.pk]),
            {"state": "new"},
            format="json",
        )

        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        own_order.refresh_from_db()
        self.assertEqual(own_order.state, "new")

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
