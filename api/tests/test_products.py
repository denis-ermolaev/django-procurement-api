from django.urls import reverse
from rest_framework import status

from api.filters import ProductFilter
from api.models import Parameter, ProductInfo, ProductParameter
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

    def test_product_list_returns_shared_product_once_when_multiple_offers_match(
        self,
    ) -> None:
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
            reverse("products"), {"price_min": 90, "price_max": 110}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product_ids = [product["id"] for product in response.data["results"]]
        self.assertEqual(product_ids.count(self.product.pk), 1)
        self.assertIn(self.product.pk, product_ids)

    def test_product_list_combines_shop_and_price_filters_on_same_offer(
        self,
    ) -> None:
        ProductInfo.objects.create(
            product=self.product,
            shop=self.other_shop,
            name="Test Phone expensive offer",
            quantity=7,
            price=1000,
            price_rrc=1100,
        )
        self.authenticate()

        response = self.api_client.get(
            reverse("products"), {"shop_id": self.other_shop.pk, "price_max": 100}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_product_list_combines_price_range_on_same_offer(self) -> None:
        ProductInfo.objects.create(
            product=self.product,
            shop=self.other_shop,
            name="Test Phone expensive offer",
            quantity=7,
            price=200,
            price_rrc=220,
        )
        self.authenticate()

        response = self.api_client.get(
            reverse("products"), {"price_min": 150, "price_max": 150}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_product_list_combines_shop_and_parameter_filters_on_same_offer(
        self,
    ) -> None:
        other_offer = ProductInfo.objects.create(
            product=self.product,
            shop=self.other_shop,
            name="Test Phone white offer",
            quantity=7,
            price=95,
            price_rrc=115,
        )
        color = Parameter.objects.get(name="color")
        ProductParameter.objects.create(
            product_info=other_offer,
            parameter=color,
            value="white",
        )
        self.authenticate()

        response = self.api_client.get(
            reverse("products"),
            {"shop_id": self.other_shop.pk, "parameter": "color:black"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

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

    def test_parameter_filter_without_separator_returns_original_queryset(self) -> None:
        queryset = ProductFilter.Meta.model.objects.order_by("id")
        filter_set = ProductFilter()

        filtered_queryset = filter_set.filter_by_parameter(queryset, "parameter", "bad")

        self.assertEqual(list(filtered_queryset), list(queryset))

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

    def test_offer_list_requires_authentication(self) -> None:
        response = self.api_client.get(reverse("offers"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_offer_list_returns_buyer_offer_cards(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("offers"), {"page_size": 1})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        offer = response.data["results"][0]
        self.assertEqual(offer["offer_id"], self.product_info.pk)
        self.assertEqual(offer["product_id"], self.product.pk)
        self.assertEqual(offer["product_name"], self.product.name)
        self.assertEqual(offer["offer_name"], self.product_info.name)
        self.assertEqual(offer["shop_name"], self.shop.name)
        self.assertEqual(offer["available_quantity"], 10)
        self.assertTrue(offer["can_add_to_basket"])
        self.assertEqual(offer["parameters"], [{"name": "color", "value": "black"}])
        self.assertNotIn("reserved_quantity", offer)

    def test_offer_list_filters_by_same_offer_fields(self) -> None:
        ProductInfo.objects.create(
            product=self.product,
            shop=self.other_shop,
            name="Test Phone expensive white offer",
            quantity=7,
            price=1000,
            price_rrc=1100,
        )
        self.authenticate()

        matching_response = self.api_client.get(
            reverse("offers"),
            {"shop_id": self.shop.pk, "price_max": 100, "parameter": "color:black"},
        )
        mixed_response = self.api_client.get(
            reverse("offers"),
            {
                "shop_id": self.other_shop.pk,
                "price_max": 100,
                "parameter": "color:black",
            },
        )

        self.assertEqual(matching_response.status_code, status.HTTP_200_OK)
        self.assertEqual(matching_response.data["count"], 1)
        self.assertEqual(
            matching_response.data["results"][0]["offer_id"],
            self.product_info.pk,
        )
        self.assertEqual(mixed_response.status_code, status.HTTP_200_OK)
        self.assertEqual(mixed_response.data["count"], 0)

    def test_offer_list_filters_by_search_category_and_stock(self) -> None:
        self.product_info.reserved_quantity = self.product_info.quantity
        self.product_info.save(update_fields=["reserved_quantity"])
        self.authenticate()

        response = self.api_client.get(
            reverse("offers"),
            {
                "search": "laptop",
                "category_id": self.other_category.pk,
                "in_stock": "true",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["offer_id"],
            self.other_product_info.pk,
        )

    def test_offer_detail_returns_offer_and_hides_unavailable(self) -> None:
        hidden_offer = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            name="Hidden offer",
            quantity=3,
            price=90,
            price_rrc=100,
            status="hidden",
        )
        self.authenticate()

        response = self.api_client.get(
            reverse("offer-detail", args=[self.product_info.pk])
        )
        hidden_response = self.api_client.get(
            reverse("offer-detail", args=[hidden_offer.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["offer_id"], self.product_info.pk)
        self.assertEqual(hidden_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_paused_shop_offer_is_hidden_and_cannot_be_added_to_basket(self) -> None:
        self.shop.is_accepting_orders = False
        self.shop.save(update_fields=["is_accepting_orders"])
        self.authenticate()

        list_response = self.api_client.get(reverse("offers"))
        detail_response = self.api_client.get(
            reverse("offer-detail", args=[self.product_info.pk])
        )
        basket_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 1},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(basket_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_product_offers_returns_offers_for_selected_product(self) -> None:
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
            reverse("product-offers", args=[self.product.pk])
        )
        missing_response = self.api_client.get(
            reverse("product-offers", args=[999_999])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        product_ids = {offer["product_id"] for offer in response.data["results"]}
        self.assertEqual(product_ids, {self.product.pk})
        self.assertEqual(missing_response.status_code, status.HTTP_404_NOT_FOUND)
