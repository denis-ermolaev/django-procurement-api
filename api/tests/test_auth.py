from django.core import mail
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from api.models import User


class AuthenticationAPITests(TestCase):
    def setUp(self) -> None:
        self.api_client = APIClient()

    def test_user_registration_uses_buyer_type_by_default(self) -> None:
        response = self.api_client.post(
            "/api/auth/users/",
            {
                "first_name": "New",
                "last_name": "Buyer",
                "email": "new@example.com",
                "password": "strong-test-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.type, "buyer")
        self.assertFalse(user.is_active)
        self.assertNotIn("password", response.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_active_user_can_obtain_jwt_and_read_profile(self) -> None:
        user = User.objects.create_user(
            email="active@example.com",
            password="strong-test-password",
            is_active=True,
        )

        token_response = self.api_client.post(
            "/api/auth/jwt/create/",
            {"email": user.email, "password": "strong-test-password"},
            format="json",
        )

        self.assertEqual(token_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", token_response.data)
        self.assertIn("refresh", token_response.data)

        self.api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}"
        )
        profile_response = self.api_client.get("/api/auth/users/me/")
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data["email"], user.email)

    def test_inactive_user_cannot_obtain_jwt(self) -> None:
        user = User.objects.create_user(
            email="inactive@example.com",
            password="strong-test-password",
        )

        response = self.api_client.post(
            "/api/auth/jwt/create/",
            {"email": user.email, "password": "strong-test-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
