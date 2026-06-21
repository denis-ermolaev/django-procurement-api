from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from api.models import Category, Product, ProductInfo, ProductParameter, Shop


class LoadShopDataCommandTests(TestCase):
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

    def test_load_shop_data_requires_shop_name(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "bad.yaml"
            yaml_path.write_text("goods: []\n", encoding="utf-8")

            with self.assertRaises(CommandError):
                call_command("load_shop_data", str(yaml_path), stdout=StringIO())
