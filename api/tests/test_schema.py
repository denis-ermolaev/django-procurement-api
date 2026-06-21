from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class OpenAPIDocumentationTests(TestCase):
    def test_schema_and_swagger_are_publicly_available(self) -> None:
        client = APIClient()

        schema_response = client.get(reverse("schema"))
        docs_response = client.get(reverse("swagger-ui"))

        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        self.assertEqual(docs_response.status_code, status.HTTP_200_OK)
