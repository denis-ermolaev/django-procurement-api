from django.urls import reverse
from rest_framework import status

from api.models import Category, Order, OrderItem, Parameter, Product, User
from api.tests.base import APITestCase


class RoleAccessAPITests(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.shop_user = User.objects.create_user(
            email="role-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            email="role-admin@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.shop.owner = self.shop_user
        self.shop.save(update_fields=["owner"])

    def test_buyer_endpoints_reject_shop_and_admin_roles(self) -> None:
        for user in (self.shop_user, self.admin_user):
            with self.subTest(user=user.email):
                self.api_client.force_authenticate(user=user)
                response = self.api_client.get(reverse("basket"))
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_endpoints_reject_buyer(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("admin-users"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ShopOfferAPITests(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.shop_user = User.objects.create_user(
            email="seller@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = self.shop_user
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])

    def test_shop_can_read_profile_and_manage_own_offers(self) -> None:
        self.api_client.force_authenticate(user=self.shop_user)

        profile_response = self.api_client.get(reverse("shop-profile"))
        update_profile_response = self.api_client.patch(
            reverse("shop-profile"),
            {"name": "Updated shop"},
            format="json",
        )
        create_response = self.api_client.post(
            reverse("shop-offers"),
            {
                "product": self.product.pk,
                "name": "Seller offer",
                "quantity": 3,
                "price": 90,
                "price_rrc": 100,
            },
            format="json",
        )
        offer_id = create_response.data["id"]
        update_offer_response = self.api_client.patch(
            reverse("shop-offer-detail", args=[offer_id]),
            {"price": 95, "status": "hidden"},
            format="json",
        )

        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_profile_response.data["name"], "Updated shop")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["shop"], self.shop.pk)
        self.assertEqual(update_offer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_offer_response.data["price"], 95)
        self.assertEqual(update_offer_response.data["status"], "hidden")

    def test_pending_shop_cannot_create_offer(self) -> None:
        self.shop.status = "pending"
        self.shop.save(update_fields=["status"])
        self.api_client.force_authenticate(user=self.shop_user)

        list_response = self.api_client.get(reverse("shop-offers"))
        response = self.api_client.post(
            reverse("shop-offers"),
            {
                "product": self.product.pk,
                "name": "Pending offer",
                "quantity": 3,
                "price": 90,
                "price_rrc": 100,
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_shop_cannot_update_another_shop_offer(self) -> None:
        self.api_client.force_authenticate(user=self.shop_user)

        response = self.api_client.patch(
            reverse("shop-offer-detail", args=[self.other_product_info.pk]),
            {"price": 95},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ShopOrderItemAPITests(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.shop_user = User.objects.create_user(
            email="order-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = self.shop_user
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])

    def create_confirmed_item(self) -> tuple[Order, OrderItem]:
        order = Order.objects.create(user=self.user, state="confirmed")
        item = OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=2,
            state="confirmed",
        )
        self.product_info.reserved_quantity = 2
        self.product_info.save(update_fields=["reserved_quantity"])
        return order, item

    def test_shop_updates_own_order_item_status_forward(self) -> None:
        order, item = self.create_confirmed_item()
        self.api_client.force_authenticate(user=self.shop_user)

        accepted_response = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item.pk]),
            {"state": "accepted"},
            format="json",
        )
        assembled_response = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item.pk]),
            {"state": "assembled"},
            format="json",
        )
        sent_response = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item.pk]),
            {"state": "sent"},
            format="json",
        )

        self.assertEqual(accepted_response.status_code, status.HTTP_200_OK)
        self.assertEqual(assembled_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sent_response.status_code, status.HTTP_200_OK)
        item.refresh_from_db()
        order.refresh_from_db()
        self.product_info.refresh_from_db()
        self.assertEqual(item.state, "sent")
        self.assertEqual(order.state, "sent")
        self.assertEqual(self.product_info.reserved_quantity, 0)
        self.assertEqual(self.product_info.quantity, 8)

    def test_shop_cancels_item_before_shipping_and_releases_reserve(self) -> None:
        order, item = self.create_confirmed_item()
        self.api_client.force_authenticate(user=self.shop_user)

        response = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item.pk]),
            {"state": "canceled"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item.refresh_from_db()
        order.refresh_from_db()
        self.product_info.refresh_from_db()
        self.assertEqual(item.state, "canceled")
        self.assertEqual(order.state, "canceled")
        self.assertEqual(self.product_info.reserved_quantity, 0)


class AdminAPITests(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.admin_user = User.objects.create_user(
            email="admin-api@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )

    def authenticate_admin(self) -> None:
        self.api_client.force_authenticate(user=self.admin_user)

    def test_admin_manages_catalog_and_offer_status(self) -> None:
        self.authenticate_admin()

        category_response = self.api_client.post(
            reverse("admin-categories"),
            {"name": "Accessories", "status": "active"},
            format="json",
        )
        product_response = self.api_client.post(
            reverse("admin-products"),
            {
                "name": "USB Cable",
                "category": category_response.data["id"],
                "status": "active",
            },
            format="json",
        )
        offer_response = self.api_client.patch(
            reverse("admin-offer-detail", args=[self.product_info.pk]),
            {"status": "blocked"},
            format="json",
        )

        self.assertEqual(category_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(product_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(offer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(offer_response.data["status"], "blocked")
        self.assertTrue(Category.objects.filter(name="Accessories").exists())
        self.assertTrue(Product.objects.filter(name="USB Cable").exists())

    def test_admin_offer_rejects_negative_price_rrc(self) -> None:
        self.authenticate_admin()

        response = self.api_client.patch(
            reverse("admin-offer-detail", args=[self.product_info.pk]),
            {"price_rrc": -1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.price_rrc, 120)

    def test_admin_lists_and_updates_reference_entities(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=1,
            state="confirmed",
        )
        self.authenticate_admin()

        list_names = (
            "admin-users",
            "admin-shops",
            "admin-categories",
            "admin-products",
            "admin-parameters",
            "admin-offers",
            "admin-orders",
        )
        for name in list_names:
            with self.subTest(name=name):
                response = self.api_client.get(reverse(name), {"page_size": 100})
                self.assertEqual(response.status_code, status.HTTP_200_OK)

        category_response = self.api_client.patch(
            reverse("admin-category-detail", args=[self.category.pk]),
            {"status": "archived"},
            format="json",
        )
        product_response = self.api_client.patch(
            reverse("admin-product-detail", args=[self.product.pk]),
            {"status": "archived"},
            format="json",
        )
        parameter_create_response = self.api_client.post(
            reverse("admin-parameters"),
            {"name": "weight"},
            format="json",
        )
        parameter_update_response = self.api_client.patch(
            reverse(
                "admin-parameter-detail", args=[parameter_create_response.data["id"]]
            ),
            {"name": "weight_kg"},
            format="json",
        )

        self.assertEqual(category_response.status_code, status.HTTP_200_OK)
        self.assertEqual(category_response.data["status"], "archived")
        self.assertEqual(product_response.status_code, status.HTTP_200_OK)
        self.assertEqual(product_response.data["status"], "archived")
        self.assertEqual(parameter_create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(parameter_update_response.status_code, status.HTTP_200_OK)
        self.assertTrue(Parameter.objects.filter(name="weight_kg").exists())

    def test_admin_cancel_order_requires_reason_and_releases_reserve(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=2,
            state="confirmed",
        )
        self.product_info.reserved_quantity = 2
        self.product_info.save(update_fields=["reserved_quantity"])
        self.authenticate_admin()

        missing_reason_response = self.api_client.patch(
            reverse("admin-order-detail", args=[order.pk]),
            {"state": "canceled"},
            format="json",
        )
        response = self.api_client.patch(
            reverse("admin-order-detail", args=[order.pk]),
            {"state": "canceled", "cancellation_reason": "Ошибочный заказ"},
            format="json",
        )

        self.assertEqual(
            missing_reason_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.product_info.refresh_from_db()
        self.assertEqual(order.state, "canceled")
        self.assertEqual(order.cancellation_reason, "Ошибочный заказ")
        self.assertEqual(self.product_info.reserved_quantity, 0)

    def test_admin_cannot_return_order_item_to_basket_state(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        item = OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=1,
            state="confirmed",
        )
        self.authenticate_admin()

        response = self.api_client.patch(
            reverse("admin-order-item-detail", args=[item.pk]),
            {"state": "basket"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        item.refresh_from_db()
        self.assertEqual(item.state, "confirmed")

    def test_admin_order_item_delivery_ships_stock_and_rejects_rollback(self) -> None:
        order = Order.objects.create(user=self.user, state="confirmed")
        item = OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=1,
            state="confirmed",
        )
        self.product_info.reserved_quantity = 1
        self.product_info.save(update_fields=["reserved_quantity"])
        self.authenticate_admin()

        delivered_response = self.api_client.patch(
            reverse("admin-order-item-detail", args=[item.pk]),
            {"state": "delivered"},
            format="json",
        )
        rollback_response = self.api_client.patch(
            reverse("admin-order-item-detail", args=[item.pk]),
            {"state": "accepted"},
            format="json",
        )

        self.assertEqual(delivered_response.status_code, status.HTTP_200_OK)
        self.assertEqual(rollback_response.status_code, status.HTTP_400_BAD_REQUEST)
        item.refresh_from_db()
        order.refresh_from_db()
        self.product_info.refresh_from_db()
        self.assertEqual(item.state, "delivered")
        self.assertEqual(order.state, "delivered")
        self.assertEqual(self.product_info.reserved_quantity, 0)
        self.assertEqual(self.product_info.quantity, 9)

    def test_admin_can_update_user_role_and_shop_status(self) -> None:
        response = self.api_client.patch(
            reverse("admin-user-detail", args=[self.user.pk]),
            {"type": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.authenticate_admin()
        invalid_response = self.api_client.patch(
            reverse("admin-user-detail", args=[self.user.pk]),
            {"type": "admin"},
            format="json",
        )
        valid_response = self.api_client.patch(
            reverse("admin-user-detail", args=[self.user.pk]),
            {"type": "admin", "is_staff": True},
            format="json",
        )
        shop_response = self.api_client.patch(
            reverse("admin-shop-detail", args=[self.shop.pk]),
            {"status": "blocked"},
            format="json",
        )

        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(valid_response.status_code, status.HTTP_200_OK)
        self.assertEqual(valid_response.data["type"], "admin")
        self.assertEqual(shop_response.status_code, status.HTTP_200_OK)
        self.assertEqual(shop_response.data["status"], "blocked")

    def test_admin_user_role_changes_preserve_role_invariants(self) -> None:
        plain_user = User.objects.create_user(
            email="plain@example.com",
            password="test-password",
            is_active=True,
        )
        shop_user = User.objects.create_user(
            email="owned-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.save(update_fields=["owner"])
        self.authenticate_admin()

        shop_without_profile_response = self.api_client.patch(
            reverse("admin-user-detail", args=[plain_user.pk]),
            {"type": "shop"},
            format="json",
        )
        owner_role_change_response = self.api_client.patch(
            reverse("admin-user-detail", args=[shop_user.pk]),
            {"type": "buyer"},
            format="json",
        )
        admin_staff_drop_response = self.api_client.patch(
            reverse("admin-user-detail", args=[self.admin_user.pk]),
            {"is_staff": False},
            format="json",
        )

        self.assertEqual(
            shop_without_profile_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            owner_role_change_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            admin_staff_drop_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
