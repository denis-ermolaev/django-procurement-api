from django.urls import reverse
from rest_framework import status

from api.models import Order, OrderItem, ProductInfo
from api.tests.base import APITestCase


class BasketAPITests(APITestCase):
    def test_get_empty_basket(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("basket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {"id": None, "state": "basket", "items": [], "total": 0},
        )

    def test_add_product_creates_basket_and_repeated_add_increases_quantity(
        self,
    ) -> None:
        self.authenticate()
        payload = {"offer_id": self.product_info.pk, "quantity": 2}

        first_response = self.api_client.post(
            reverse("basket-items"), payload, format="json"
        )
        second_response = self.api_client.post(
            reverse("basket-items"), payload, format="json"
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(user=self.user, state="basket")
        item = OrderItem.objects.get(order=order, product_info=self.product_info)
        self.assertEqual(item.quantity, 4)
        self.assertEqual(second_response.data["data"]["quantity"], 4)
        self.assertEqual(second_response.data["data"]["line_total"], 400)

    def test_add_item_resource_accepts_offer_id(self) -> None:
        self.authenticate()

        response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["offer_id"], self.product_info.pk)
        self.assertEqual(response.data["data"]["product_name"], self.product.name)
        self.assertEqual(response.data["data"]["line_total"], 200)

    def test_add_product_validates_payload_and_missing_offer(self) -> None:
        self.authenticate()
        invalid_payloads = (
            {"offer_id": self.product_info.pk, "quantity": 0},
            {"offer_id": self.product_info.pk},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.api_client.post(
                    reverse("basket-items"), payload, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        missing_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": 999_999, "quantity": 1},
            format="json",
        )
        self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Order.objects.filter(user=self.user, state="basket").exists())

    def test_add_product_rejects_quantity_above_available_stock(self) -> None:
        self.authenticate()

        too_many_response = self.api_client.post(
            reverse("basket-items"),
            {
                "offer_id": self.product_info.pk,
                "quantity": self.product_info.quantity + 1,
            },
            format="json",
        )
        valid_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 9},
            format="json",
        )
        overflow_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )

        self.assertEqual(too_many_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED)
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
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        second_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": second_shop_offer.pk, "quantity": 3},
            format="json",
        )
        basket_response = self.api_client.get(reverse("basket"))

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(basket_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(basket_response.data["items"]), 2)
        basket_by_offer = {
            item["offer_id"]: item["quantity"] for item in basket_response.data["items"]
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
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["id"], own_item.pk)

    def test_get_basket_returns_current_basket_only(self) -> None:
        current_order = Order.objects.create(user=self.user, state="basket")
        current_item = OrderItem.objects.create(
            order=current_order, product_info=self.product_info, quantity=2
        )
        confirmed_order = Order.objects.create(user=self.user, state="confirmed")
        OrderItem.objects.create(
            order=confirmed_order, product_info=self.product_info, quantity=1
        )
        self.authenticate()

        response = self.api_client.get(reverse("basket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], current_order.pk)
        self.assertEqual(response.data["state"], "basket")
        self.assertEqual(response.data["total"], 200)
        self.assertEqual(response.data["items"][0]["id"], current_item.pk)
        self.assertEqual(response.data["items"][0]["offer_id"], self.product_info.pk)
        self.assertEqual(response.data["items"][0]["quantity"], 2)
        self.assertEqual(response.data["items"][0]["warnings"], [])

    def test_patch_item_resource_updates_quantity(self) -> None:
        order = Order.objects.create(user=self.user, state="basket")
        item = OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2
        )
        self.authenticate()

        response = self.api_client.patch(
            reverse("basket-item-detail", args=[item.pk]),
            {"quantity": 4},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)
        self.assertEqual(response.data["data"]["line_total"], 400)

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
            reverse("basket-item-detail", args=[other_item.pk])
        )
        response = self.api_client.delete(
            reverse("basket-item-detail", args=[own_item.pk])
        )

        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OrderItem.objects.filter(id=own_item.pk).exists())

    def test_delete_basket_without_query_clears_current_basket(self) -> None:
        order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2
        )
        OrderItem.objects.create(
            order=order, product_info=self.other_product_info, quantity=1
        )
        self.authenticate()

        response = self.api_client.delete(reverse("basket"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OrderItem.objects.filter(order=order).exists())

    def test_delete_item_rejects_non_basket_order(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        item = OrderItem.objects.create(
            order=order, product_info=self.product_info, quantity=2
        )
        self.authenticate()

        response = self.api_client.delete(reverse("basket-item-detail", args=[item.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(OrderItem.objects.filter(id=item.pk).exists())
