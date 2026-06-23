from django.db import IntegrityError, transaction
from django.test import TestCase

from api.models import (
    Category,
    Contact,
    Order,
    OrderItem,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)


class UserManagerTests(TestCase):
    def test_create_user_requires_email(self) -> None:
        with self.assertRaisesMessage(ValueError, "email"):
            User.objects.create_user(email="", password="test-password")

    def test_create_superuser_requires_staff_and_superuser_flags(self) -> None:
        with self.assertRaisesMessage(ValueError, "is_staff=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="test-password",
                is_staff=False,
            )

        with self.assertRaisesMessage(ValueError, "is_superuser=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="test-password",
                is_superuser=False,
            )

    def test_create_superuser_sets_staff_and_superuser_flags(self) -> None:
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="test-password",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.type, "admin")

    def test_create_superuser_requires_admin_type(self) -> None:
        with self.assertRaisesMessage(ValueError, "type='admin'"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="test-password",
                type="buyer",
            )


class ModelStringRepresentationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="test-password",
            first_name="Buyer",
            is_active=True,
        )
        self.shop = Shop.objects.create(name="Main shop", url="https://shop.test")
        self.category = Category.objects.create(name="Phones")
        self.category.shops.add(self.shop)
        self.product = Product.objects.create(name="Test Phone", category=self.category)
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            name="Test Phone 128GB",
            quantity=10,
            price=100,
            price_rrc=120,
        )
        self.parameter = Parameter.objects.create(name="color")
        self.product_parameter = ProductParameter.objects.create(
            product_info=self.product_info,
            parameter=self.parameter,
            value="black",
        )
        self.contact = Contact.objects.create(
            user=self.user,
            city="Kaliningrad",
            street="Lenina",
            house="1",
            phone="+70000000000",
        )
        self.order = Order.objects.create(
            user=self.user,
            state="confirmed",
            contact=self.contact,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product_info=self.product_info,
            quantity=2,
        )

    def test_user_string_prefers_full_name_and_falls_back_to_email(self) -> None:
        unnamed_user = User.objects.create_user(
            email="unnamed@example.com",
            password="test-password",
            is_active=True,
        )

        self.assertEqual(str(self.user), "Buyer")
        self.assertEqual(str(unnamed_user), "unnamed@example.com")

    def test_catalog_models_have_readable_string_representation(self) -> None:
        self.assertEqual(str(self.shop), "Main shop")
        self.assertEqual(str(self.category), "Phones")
        self.assertEqual(str(self.product), "Test Phone")
        self.assertEqual(str(self.product_info), "Test Phone 128GB (Main shop)")
        self.assertEqual(str(self.parameter), "color")
        self.assertEqual(str(self.product_parameter), "color: black")

    def test_order_models_have_readable_string_representation(self) -> None:
        self.assertEqual(
            str(self.contact),
            "Kaliningrad, Lenina, +70000000000",
        )
        self.assertEqual(str(self.order), f"Order #{self.order.pk} (confirmed)")
        self.assertEqual(str(self.order_item), "Test Phone 128GB (Main shop) x 2")


class DomainConstraintTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="buyer@example.com",
            password="test-password",
            is_active=True,
        )
        self.shop = Shop.objects.create(name="Main shop", status="active")
        self.category = Category.objects.create(name="Phones")
        self.category.shops.add(self.shop)
        self.product = Product.objects.create(name="Test Phone", category=self.category)
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            name="Test Phone 128GB",
            quantity=10,
            reserved_quantity=2,
            price=100,
            price_rrc=120,
        )

    def test_product_info_rejects_invalid_numeric_values(self) -> None:
        invalid_values = (
            {"quantity": -1, "reserved_quantity": 0, "price": 100, "price_rrc": 120},
            {"quantity": 1, "reserved_quantity": 2, "price": 100, "price_rrc": 120},
            {"quantity": 1, "reserved_quantity": 0, "price": 0, "price_rrc": 120},
            {"quantity": 1, "reserved_quantity": 0, "price": 100, "price_rrc": -1},
        )

        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    ProductInfo.objects.create(
                        product=self.product,
                        shop=self.shop,
                        name="Invalid offer",
                        **values,
                    )

    def test_order_item_rejects_non_positive_quantity(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")

        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=order,
                product_info=self.product_info,
                quantity=0,
                state="confirmed",
            )

    def test_user_has_single_active_basket(self) -> None:
        Order.objects.create(user=self.user, state="basket")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(user=self.user, state="basket")

        Order.objects.create(user=self.user, state="confirmed")
        self.assertEqual(Order.objects.filter(user=self.user).count(), 2)

    def test_order_item_offer_is_unique_inside_order(self) -> None:
        order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=1,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=order,
                product_info=self.product_info,
                quantity=1,
            )

    def test_offer_external_id_is_unique_per_shop_when_filled(self) -> None:
        ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            external_id="offer-1",
            name="Offer 1",
            quantity=1,
            price=100,
            price_rrc=120,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductInfo.objects.create(
                product=self.product,
                shop=self.shop,
                external_id="offer-1",
                name="Offer duplicate",
                quantity=1,
                price=100,
                price_rrc=120,
            )

    def test_parameter_name_and_offer_parameter_are_unique(self) -> None:
        parameter = Parameter.objects.create(name="color")
        ProductParameter.objects.create(
            product_info=self.product_info,
            parameter=parameter,
            value="black",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Parameter.objects.create(name="color")

        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductParameter.objects.create(
                product_info=self.product_info,
                parameter=parameter,
                value="white",
            )
