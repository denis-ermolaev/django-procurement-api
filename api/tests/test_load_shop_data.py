from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.models import Category, Product, ProductInfo, ProductParameter, Shop, User


class LoadShopDataCommandTests(TestCase):
    data_dir = Path(__file__).resolve().parents[2] / "data"
    yaml_data = """
shop: Test shop
url: https://shop.example.com
categories:
  - id: 1
    name: Phones
goods:
  - id: 100
    category: 1
    model: test/phone
    name: Test Phone
    price: 100
    price_rrc: 120
    quantity: 5
    parameters:
      color: black
      memory: 128
"""

    def test_load_shop_data_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "shop.yaml"
            yaml_path.write_text(self.yaml_data, encoding="utf-8")

            call_command("load_shop_data", str(yaml_path), stdout=StringIO())
            call_command("load_shop_data", str(yaml_path), stdout=StringIO())

        self.assertEqual(Shop.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductInfo.objects.count(), 1)
        self.assertEqual(ProductParameter.objects.count(), 2)
        product_info = ProductInfo.objects.get()
        self.assertEqual(product_info.quantity, 5)
        self.assertEqual(product_info.external_id, "100")
        self.assertEqual(product_info.model, "test/phone")
        self.assertEqual(product_info.shop.url, "https://shop.example.com")
        self.assertEqual(product_info.shop.status, "active")

    def test_load_shop_data_updates_offer_by_external_id_after_rename(self) -> None:
        renamed_yaml = self.yaml_data.replace("Test Phone", "Renamed Phone").replace(
            "price: 100",
            "price: 150",
        )

        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "shop.yaml"
            yaml_path.write_text(self.yaml_data, encoding="utf-8")
            call_command("load_shop_data", str(yaml_path), stdout=StringIO())

            yaml_path.write_text(renamed_yaml, encoding="utf-8")
            call_command("load_shop_data", str(yaml_path), stdout=StringIO())

        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductInfo.objects.count(), 1)
        product = Product.objects.get()
        product_info = ProductInfo.objects.get()
        self.assertEqual(product.name, "Renamed Phone")
        self.assertEqual(product_info.name, "Renamed Phone")
        self.assertEqual(product_info.external_id, "100")
        self.assertEqual(product_info.price, 150)

    def test_repository_shop_fixtures_load_two_shops_without_duplicates(self) -> None:
        shop1_path = self.data_dir / "shop1.yaml"
        shop2_path = self.data_dir / "shop2.yaml"

        call_command("load_shop_data", str(shop1_path), stdout=StringIO())
        call_command("load_shop_data", str(shop2_path), stdout=StringIO())
        call_command("load_shop_data", str(shop2_path), stdout=StringIO())

        self.assertEqual(Shop.objects.count(), 2)
        self.assertEqual(Category.objects.count(), 6)
        self.assertEqual(Product.objects.count(), 18)
        self.assertEqual(ProductInfo.objects.count(), 20)

        client = APIClient()
        user = User.objects.create_user(
            email="buyer@example.com",
            password="test-password",
            is_active=True,
        )
        client.force_authenticate(user=user)
        response = client.get("/api/products/", {"page_size": 100})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 18)

        shared_products = {
            "Смартфон Apple iPhone XR 256GB (черный)": [63000, 65000],
            "Smartphone Xiaomi Mi 10T Pro 256GB (cosmic black)": [68000, 70000],
        }
        for product_name, expected_prices in shared_products.items():
            with self.subTest(product_name=product_name):
                shared_product = Product.objects.get(name=product_name)
                offers = ProductInfo.objects.filter(product=shared_product).order_by(
                    "price"
                )

                self.assertEqual(offers.count(), 2)
                self.assertEqual(
                    [offer.shop.name for offer in offers], ["ТехноМаркет", "Связной"]
                )
                self.assertEqual([offer.price for offer in offers], expected_prices)

    def test_load_shop_data_requires_shop_name(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "bad.yaml"
            yaml_path.write_text("goods: []\n", encoding="utf-8")

            with self.assertRaises(CommandError):
                call_command("load_shop_data", str(yaml_path), stdout=StringIO())

    def test_load_shop_data_updates_existing_shop_url(self) -> None:
        updated_yaml = self.yaml_data.replace(
            "https://shop.example.com", "https://updated.example.com"
        )

        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "shop.yaml"
            yaml_path.write_text(self.yaml_data, encoding="utf-8")
            call_command("load_shop_data", str(yaml_path), stdout=StringIO())

            yaml_path.write_text(updated_yaml, encoding="utf-8")
            call_command("load_shop_data", str(yaml_path), stdout=StringIO())

        self.assertEqual(Shop.objects.count(), 1)
        self.assertEqual(Shop.objects.get().url, "https://updated.example.com")

    def test_load_shop_data_reactivates_seed_entities_for_api_visibility(self) -> None:
        shop = Shop.objects.create(
            name="Test shop",
            url="https://old.example.com",
            status="pending",
        )
        category = Category.objects.create(name="Phones", status="archived")
        category.shops.add(shop)
        product = Product.objects.create(
            name="Test Phone",
            category=category,
            status="archived",
        )
        ProductInfo.objects.create(
            product=product,
            shop=shop,
            name="Test Phone",
            quantity=1,
            price=50,
            price_rrc=60,
            status="hidden",
        )

        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "shop.yaml"
            yaml_path.write_text(self.yaml_data, encoding="utf-8")
            call_command("load_shop_data", str(yaml_path), stdout=StringIO())

        shop.refresh_from_db()
        category.refresh_from_db()
        product.refresh_from_db()
        product_info = ProductInfo.objects.get(product=product, shop=shop)
        self.assertEqual(shop.status, "active")
        self.assertEqual(category.status, "active")
        self.assertEqual(product.status, "active")
        self.assertEqual(product_info.status, "active")

        client = APIClient()
        user = User.objects.create_user(
            email="buyer@example.com",
            password="test-password",
            is_active=True,
        )
        client.force_authenticate(user=user)
        response = client.get("/api/products/", {"page_size": 100})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_load_shop_data_skips_goods_with_unknown_category(self) -> None:
        yaml_data = """
shop: Test shop
categories:
  - id: 1
    name: Phones
goods:
  - id: 100
    category: 999
    name: Skipped Phone
    price: 100
    price_rrc: 120
    quantity: 5
"""

        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "shop.yaml"
            yaml_path.write_text(yaml_data, encoding="utf-8")
            stderr = StringIO()

            call_command(
                "load_shop_data", str(yaml_path), stdout=StringIO(), stderr=stderr
            )

        self.assertEqual(Product.objects.count(), 0)
        self.assertIn("Category id 999 not found", stderr.getvalue())

    def test_shop_import_api_updates_offers_atomically(self) -> None:
        shop_user = User.objects.create_user(
            email="shop-import@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        Shop.objects.create(owner=shop_user, name="Test shop", status="active")
        client = APIClient()
        client.force_authenticate(user=shop_user)

        response = client.post(
            reverse("shop-imports"),
            {"content": self.yaml_data},
            format="json",
        )
        bad_response = client.post(
            reverse("shop-imports"),
            {"content": self.yaml_data.replace("price: 100", "price: 0")},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["loaded_count"], 1)
        self.assertEqual(response.data["created_offers"], 1)
        self.assertEqual(bad_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ProductInfo.objects.count(), 1)
        self.assertEqual(ProductInfo.objects.get().external_id, "100")

    def test_shop_import_api_requires_shop_role(self) -> None:
        buyer = User.objects.create_user(
            email="buyer-import@example.com",
            password="test-password",
            is_active=True,
        )
        client = APIClient()
        client.force_authenticate(user=buyer)

        response = client.post(
            reverse("shop-imports"),
            {"content": self.yaml_data},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
