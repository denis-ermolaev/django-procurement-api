from django.urls import reverse
from rest_framework import status

from api.models import Contact
from api.tests.base import APITestCase


class ContactAPITests(APITestCase):
    contact_payload = {
        "city": "Kaliningrad",
        "street": "Lenina",
        "house": "1",
        "structure": "",
        "building": "",
        "apartment": "10",
        "phone": "+70000000000",
    }

    def test_create_and_list_contacts(self) -> None:
        self.authenticate()

        create_response = self.api_client.post(
            reverse("contact"), self.contact_payload, format="json"
        )
        list_response = self.api_client.get(reverse("contact"))

        self.assertEqual(create_response.status_code, status.HTTP_200_OK)
        contact = Contact.objects.get(user=self.user)
        self.assertEqual(create_response.data["data"]["id"], contact.pk)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["data"][0]["city"], "Kaliningrad")

    def test_create_contact_validates_required_fields(self) -> None:
        self.authenticate()

        response = self.api_client.post(
            reverse("contact"), {"city": "Kaliningrad"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("street", response.data)
        self.assertIn("phone", response.data)

    def test_empty_contact_list_returns_empty_data(self) -> None:
        self.authenticate()

        response = self.api_client.get(reverse("contact"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"data": []})

    def test_delete_contact_checks_ownership(self) -> None:
        own_contact = Contact.objects.create(user=self.user, **self.contact_payload)
        other_contact = Contact.objects.create(
            user=self.other_user, **self.contact_payload
        )
        self.authenticate()

        forbidden_response = self.api_client.delete(
            f"{reverse('contact')}?id={other_contact.pk}"
        )
        response = self.api_client.delete(f"{reverse('contact')}?id={own_contact.pk}")

        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Contact.objects.filter(id=own_contact.pk).exists())
