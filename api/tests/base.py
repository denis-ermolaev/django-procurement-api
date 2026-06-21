from django.test import TestCase
from rest_framework.test import APIClient

from api.models import (
    Category,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)


class APITestCase(TestCase):
    api_client: APIClient
    user: User
    other_user: User
    shop: Shop
    other_shop: Shop
    category: Category
    other_category: Category
    product: Product
    other_product: Product
    product_info: ProductInfo
    other_product_info: ProductInfo

    def setUp(self) -> None:
        self.api_client = APIClient()
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="test-password",
            first_name="Buyer",
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="test-password",
            is_active=True,
        )
        self.shop = Shop.objects.create(name="Main shop", url="https://shop.test")
        self.other_shop = Shop.objects.create(
            name="Other shop", url="https://other-shop.test"
        )
        self.category = Category.objects.create(name="Phones")
        self.category.shops.add(self.shop)
        self.other_category = Category.objects.create(name="Laptops")
        self.other_category.shops.add(self.other_shop)
        self.product = Product.objects.create(name="Test Phone", category=self.category)
        self.other_product = Product.objects.create(
            name="Work Laptop", category=self.other_category
        )
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            name="Test Phone 128GB",
            quantity=10,
            price=100,
            price_rrc=120,
        )
        self.other_product_info = ProductInfo.objects.create(
            product=self.other_product,
            shop=self.other_shop,
            name="Work Laptop 16GB",
            quantity=5,
            price=500,
            price_rrc=550,
        )
        color = Parameter.objects.create(name="color")
        ProductParameter.objects.create(
            product_info=self.product_info,
            parameter=color,
            value="black",
        )

    def authenticate(self, user: User | None = None) -> None:
        self.api_client.force_authenticate(user=user or self.user)
