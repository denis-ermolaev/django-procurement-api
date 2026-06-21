from django.urls import reverse
from rest_framework import status

from api.models import Order, OrderItem
from api.tests.base import APITestCase


class BasketAPITests(APITestCase):
    def test_get_empty_basket(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("basket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_add_product_creates_basket_and_repeated_add_increases_quantity(
        self,
    ) -> None:
        self.authenticate()
        payload = {"product_info_id": self.product_info.pk, "quantity": 2}

        first_response = self.api_client.post(reverse("basket"), payload, format="json")
        second_response = self.api_client.post(
            reverse("basket"), payload, format="json"
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        order = Order.objects.get(user=self.user, state="basket")
        item = OrderItem.objects.get(order=order, product_info=self.product_info)
        self.assertEqual(item.quantity, 4)
        self.assertEqual(second_response.data["data"]["quantity"], 4)

    def test_add_product_validates_payload_and_missing_offer(self) -> None:
        self.authenticate()
        invalid_payloads = (
            {"product_info_id": self.product_info.pk, "quantity": 0},
            {"product_info_id": self.product_info.pk},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.api_client.post(
                    reverse("basket"), payload, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        missing_response = self.api_client.post(
            reverse("basket"),
            {"product_info_id": 999_999, "quantity": 1},
            format="json",
        )
        self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_basket_returns_only_authenticated_users_items(self) -> None:
        own_order = Order.objects.create(user=self.user, state="basket")
        own_item = OrderItem.objects.create(
            order=own_order, product_info=self.product_info, quantity=2
        )
        other_order = Order.objects.create(user=self.other_user, state="basket")
        OrderItem.objects.create(
            order=other_order, product_info=self.other_product_info, quantity=3
        )
        self.authenticate()

        response = self.api_client.get(reverse("basket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0][0]["id"], own_item.pk)

    def test_delete_item_checks_order_ownership(self) -> None:
        own_order = Order.objects.create(user=self.user, state="basket")
        own_item = OrderItem.objects.create(
            order=own_order, product_info=self.product_info, quantity=2
        )
        other_order = Order.objects.create(user=self.other_user, state="basket")
        other_item = OrderItem.objects.create(
            order=other_order, product_info=self.other_product_info, quantity=3
        )
        self.authenticate()

        forbidden_response = self.api_client.delete(
            f"{reverse('basket')}?order_id={other_order.pk}"
            f"&product_info_id={other_item.pk}"
        )
        response = self.api_client.delete(
            f"{reverse('basket')}?order_id={own_order.pk}&product_info_id={own_item.pk}"
        )

        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OrderItem.objects.filter(id=own_item.pk).exists())
