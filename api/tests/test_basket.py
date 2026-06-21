from django.urls import reverse
from rest_framework import status

from api.models import Order, OrderItem, ProductInfo
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
        self.assertFalse(Order.objects.filter(user=self.user, state="basket").exists())

    def test_add_product_rejects_quantity_above_available_stock(self) -> None:
        self.authenticate()

        too_many_response = self.api_client.post(
            reverse("basket"),
            {
                "product_info_id": self.product_info.pk,
                "quantity": self.product_info.quantity + 1,
            },
            format="json",
        )
        valid_response = self.api_client.post(
            reverse("basket"),
            {"product_info_id": self.product_info.pk, "quantity": 9},
            format="json",
        )
        overflow_response = self.api_client.post(
            reverse("basket"),
            {"product_info_id": self.product_info.pk, "quantity": 2},
            format="json",
        )

        self.assertEqual(too_many_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(valid_response.status_code, status.HTTP_200_OK)
        self.assertEqual(overflow_response.status_code, status.HTTP_400_BAD_REQUEST)
        item = OrderItem.objects.get(
            product_info=self.product_info, order__user=self.user
        )
        self.assertEqual(item.quantity, 9)

    def test_add_shared_product_from_two_shops_creates_separate_items(self) -> None:
        second_shop_offer = ProductInfo.objects.create(
            product=self.product,
            shop=self.other_shop,
            name="Test Phone from second shop",
            quantity=7,
            price=95,
            price_rrc=115,
        )
        self.authenticate()

        first_response = self.api_client.post(
            reverse("basket"),
            {"product_info_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        second_response = self.api_client.post(
            reverse("basket"),
            {"product_info_id": second_shop_offer.pk, "quantity": 3},
            format="json",
        )
        basket_response = self.api_client.get(reverse("basket"))

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(basket_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(basket_response.data), 2)
        basket_by_offer = {
            item["product_info"]: item["quantity"] for item in basket_response.data
        }
        self.assertEqual(
            basket_by_offer,
            {
                self.product_info.pk: 2,
                second_shop_offer.pk: 3,
            },
        )

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
        self.assertEqual(response.data[0]["id"], own_item.pk)

    def test_get_basket_returns_current_basket_only(self) -> None:
        current_order = Order.objects.create(user=self.user, state="basket")
        current_item = OrderItem.objects.create(
            order=current_order, product_info=self.product_info, quantity=2
        )
        stale_order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=stale_order, product_info=self.other_product_info, quantity=3
        )
        confirmed_order = Order.objects.create(user=self.user, state="confirmed")
        OrderItem.objects.create(
            order=confirmed_order, product_info=self.product_info, quantity=1
        )
        self.authenticate()

        response = self.api_client.get(reverse("basket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            [
                {
                    "id": current_item.pk,
                    "order": current_order.pk,
                    "product_info": self.product_info.pk,
                    "quantity": 2,
                }
            ],
        )

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
            f"{reverse('basket')}?item_id={other_item.pk}"
        )
        response = self.api_client.delete(f"{reverse('basket')}?item_id={own_item.pk}")
        missing_response = self.api_client.delete(
            f"{reverse('basket')}?order_id={own_order.pk}&item_id={other_item.pk}"
        )

        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(OrderItem.objects.filter(id=own_item.pk).exists())

    def test_delete_item_rejects_non_basket_order(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        item = OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2
        )
        self.authenticate()

        response = self.api_client.delete(f"{reverse('basket')}?item_id={item.pk}")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(OrderItem.objects.filter(id=item.pk).exists())

    def test_delete_item_requires_item_identifier(self) -> None:
        self.authenticate()

        response = self.api_client.delete(reverse("basket"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("item_id", response.data)
