from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from api.models import Category, Product, ProductInfo, ProductParameter, Shop


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
        self.assertEqual(product_info.shop.url, "https://shop.example.com")

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
