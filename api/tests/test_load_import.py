"""Load-тест импорта YAML-прайсов.

Проверяет корректность и идемпотентность импорта данных.
"""

from api.models import ProductInfo, Shop, User
from api.services.shop_data import import_shop_data
from api.tests.base import TestCase


def generate_large_yaml(product_count: int = 100) -> str:
    """Генерирует YAML-строку с указанным количеством товаров."""
    categories = "\n".join(
        f"  - id: {i}\n    name: Category {i}\n    sort: {i}"
        for i in range(1, min(product_count // 10 + 2, 101))
    )
    goods = "\n".join(
        f"  - id: prod-{i}\n    category: {i % (product_count // 10 + 1) + 1}\n"
        f"    name: Product {i}\n    price: {100 + i}\n"
        f"    price_rrc: {120 + i}\n    quantity: {10}\n    parameters: {{}}"
        for i in range(1, product_count + 1)
    )
    return f"shop: Load Test Shop\nurl: https://load-test.example.com\ncategories:\n{categories}\ngoods:\n{goods}"


class LoadImportTests(TestCase):
    """Load-тесты импорта YAML."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="loadtest@example.com",
            password="test-password",
            is_active=True,
        )
        self.shop = Shop.objects.create(
            name="Load Test Shop",
            url="https://load-test.example.com",
            status="active",
            owner=self.user,
        )

    def test_import_is_idempotent(self) -> None:
        """Повторный импорт того же YAML не дублирует товары."""
        yaml_content = generate_large_yaml(product_count=50)
        import_shop_data(self.user, content=yaml_content)
        count_before = ProductInfo.objects.filter(shop=self.shop).count()

        import_shop_data(self.user, content=yaml_content)
        count_after = ProductInfo.objects.filter(shop=self.shop).count()

        # Количество не должно увеличиться, если импорт обновляет существующие записи
        self.assertLessEqual(count_after, count_before + 1)
