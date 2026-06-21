from django.urls import reverse
from rest_framework import status

from api.models import ProductInfo
from api.tests.base import APITestCase


class ProductAPITests(APITestCase):
    def test_product_list_requires_authentication(self) -> None:
        response = self.api_client.get(reverse("products"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_product_list_is_paginated(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("products"), {"page_size": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIsNotNone(response.data["next"])

    def test_product_list_filters_by_search_category_shop_and_price(self) -> None:
        self.authenticate()
        filters = (
            {"search": "phone"},
            {"category_id": self.category.pk},
            {"shop_id": self.shop.pk},
            {"price_min": 90, "price_max": 110},
            {"parameter": "color:BLACK"},
        )

        for query_params in filters:
            with self.subTest(query_params=query_params):
                response = self.api_client.get(reverse("products"), query_params)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 1)
                self.assertEqual(response.data["results"][0]["id"], self.product.pk)

    def test_product_list_filters_shared_product_by_shop_offer(self) -> None:
        ProductInfo.objects.create(
            product=self.product,
            shop=self.other_shop,
            name="Test Phone from second shop",
            quantity=7,
            price=95,
            price_rrc=115,
        )
        self.authenticate()

        response = self.api_client.get(
            reverse("products"), {"shop_id": self.other_shop.pk}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        product_ids = {product["id"] for product in response.data["results"]}
        self.assertEqual(product_ids, {self.product.pk, self.other_product.pk})

    def test_invalid_numeric_filter_returns_bad_request(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("products"), {"category_id": "bad"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category_id", response.data)

    def test_invalid_parameter_filter_returns_bad_request(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("products"), {"parameter": "bad"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parameter", response.data)

    def test_product_detail_returns_offer_and_handles_missing_id(self) -> None:
        self.authenticate()

        response = self.api_client.get(
            reverse("product-detail", args=[self.product_info.pk])
        )
        missing_response = self.api_client.get(
            reverse("product-detail", args=[999_999])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["product"], self.product.pk)
        self.assertEqual(response.data["price"], 100)
        self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)
