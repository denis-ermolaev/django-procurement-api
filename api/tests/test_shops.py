from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory

from api.models import Shop, User
from api.permissions import IsActiveShop, IsAdminUserType, IsShop
from api.tests.base import APITestCase


class ShopRegistrationAPITests(APITestCase):
    def test_shop_registration_creates_shop_user_and_pending_shop(self) -> None:
        response = self.api_client.post(
            reverse("shop-register"),
            {
                "first_name": "Shop",
                "last_name": "Owner",
                "email": "supplier@example.com",
                "password": "strong-test-password",
                "shop_name": "Supplier shop",
                "url": "https://supplier.example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="supplier@example.com")
        shop = Shop.objects.get(owner=user)
        self.assertEqual(user.type, "shop")
        self.assertFalse(user.is_active)
        self.assertEqual(shop.status, "pending")
        self.assertEqual(shop.name, "Supplier shop")
        self.assertNotIn("password", response.data["user"])
        self.assertEqual(response.data["user"]["type"], "shop")
        self.assertEqual(response.data["shop"]["owner"], user.pk)
        self.assertEqual(response.data["shop"]["status"], "pending")

    def test_shop_registration_rejects_duplicate_email(self) -> None:
        response = self.api_client.post(
            reverse("shop-register"),
            {
                "email": self.user.email,
                "password": "strong-test-password",
                "shop_name": "Duplicate supplier",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_buyer_registration_rejects_shop_and_admin_types(self) -> None:
        for user_type in ("shop", "admin"):
            with self.subTest(user_type=user_type):
                response = self.api_client.post(
                    "/api/auth/users/",
                    {
                        "first_name": "Wrong",
                        "last_name": "Role",
                        "email": f"{user_type}@example.com",
                        "password": "strong-test-password",
                        "type": user_type,
                    },
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("type", response.data)
                self.assertFalse(
                    User.objects.filter(email=f"{user_type}@example.com").exists()
                )


class AdminShopModerationAPITests(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.shop_user = User.objects.create_user(
            email="shop-user@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.pending_shop = Shop.objects.create(
            owner=self.shop_user,
            name="Pending supplier",
            url="https://pending.example.com",
            status="pending",
        )

    def test_admin_can_approve_and_block_shop(self) -> None:
        self.api_client.force_authenticate(user=self.admin_user)

        approve_response = self.api_client.post(
            reverse("admin-shop-approve", args=[self.pending_shop.pk])
        )
        block_response = self.api_client.post(
            reverse("admin-shop-block", args=[self.pending_shop.pk])
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_response.data["status"], "active")
        self.assertEqual(block_response.status_code, status.HTTP_200_OK)
        self.assertEqual(block_response.data["status"], "blocked")
        self.pending_shop.refresh_from_db()
        self.assertEqual(self.pending_shop.status, "blocked")

    def test_shop_moderation_requires_admin_role(self) -> None:
        anonymous_response = self.api_client.post(
            reverse("admin-shop-approve", args=[self.pending_shop.pk])
        )
        self.api_client.force_authenticate(user=self.user)
        buyer_response = self.api_client.post(
            reverse("admin-shop-approve", args=[self.pending_shop.pk])
        )
        self.api_client.force_authenticate(user=self.shop_user)
        shop_response = self.api_client.post(
            reverse("admin-shop-approve", args=[self.pending_shop.pk])
        )

        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(buyer_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(shop_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_shop_moderation_returns_not_found_for_missing_shop(self) -> None:
        self.api_client.force_authenticate(user=self.admin_user)

        response = self.api_client.post(reverse("admin-shop-approve", args=[999_999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class RolePermissionTests(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.factory = APIRequestFactory()
        self.shop_user = User.objects.create_user(
            email="permission-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            email="permission-admin@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )

    def request_for(self, user: User):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_shop_permission_allows_shop_user(self) -> None:
        self.assertTrue(IsShop().has_permission(self.request_for(self.shop_user), None))
        self.assertFalse(IsShop().has_permission(self.request_for(self.user), None))

    def test_active_shop_permission_requires_active_shop(self) -> None:
        Shop.objects.create(
            owner=self.shop_user,
            name="Permission supplier",
            status="pending",
        )

        self.assertFalse(
            IsActiveShop().has_permission(self.request_for(self.shop_user), None)
        )
        shop_obj = Shop.objects.get(owner=self.shop_user)
        shop_obj.status = "active"
        shop_obj.save(update_fields=["status"])
        self.assertTrue(
            IsActiveShop().has_permission(self.request_for(self.shop_user), None)
        )

    def test_active_shop_permission_denies_shop_user_without_profile(self) -> None:
        unlinked_shop_user = User.objects.create_user(
            email="unlinked-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )

        self.assertFalse(
            IsActiveShop().has_permission(self.request_for(unlinked_shop_user), None)
        )

    def test_admin_permission_requires_staff_admin_type(self) -> None:
        staff_buyer = User.objects.create_user(
            email="staff-buyer@example.com",
            password="test-password",
            type="buyer",
            is_staff=True,
            is_active=True,
        )

        self.assertTrue(
            IsAdminUserType().has_permission(self.request_for(self.admin_user), None)
        )
        self.assertFalse(
            IsAdminUserType().has_permission(self.request_for(staff_buyer), None)
        )
