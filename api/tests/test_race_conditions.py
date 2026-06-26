"""Тесты корректности бизнес-логики при конкурентных сценариях.

SQLite не поддерживает полноценный SELECT FOR UPDATE, поэтому эти тесты
проверяют корректность логики резервирования и проверки остатков без threading.
Реальные race-condition тесты требуют PostgreSQL + pytest-django-parallel.
"""

from django.urls import reverse
from rest_framework import status

from api.models import Contact, Order, OrderItem, ProductInfo
from api.tests.base import APITestCase


class BasketStockValidationTests(APITestCase):
    """Проверка что корзина не позволяет добавить больше, чем есть на складе."""

    def test_add_to_basket_rejects_when_stock_exceeded(self) -> None:
        """Нельзя добавить 5 штук при остатке 3."""
        self.authenticate()
        self.product_info.quantity = 3
        self.product_info.save(update_fields=["quantity"])

        resp = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 5},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_to_basket_allows_when_stock_sufficient(self) -> None:
        """Можно добавить 5 штук при остатке 8."""
        self.authenticate()
        self.product_info.quantity = 8
        self.product_info.save(update_fields=["quantity"])

        resp = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 5},
            format="json",
        )
        self.assertIn(
            resp.status_code,
            [status.HTTP_200_OK, status.HTTP_201_CREATED],
        )

    def test_update_basket_item_rejects_when_stock_exceeded(self) -> None:
        """Нельзя увеличить количество до 10 при остатке 5."""
        self.authenticate()
        self.product_info.quantity = 5
        self.product_info.save(update_fields=["quantity"])

        # Сначала добавляем 3
        add_resp = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 3},
            format="json",
        )
        item_id = add_resp.data["data"]["id"]

        # Пытаемся увеличить до 10
        update_resp = self.api_client.patch(
            reverse("basket-item-detail", args=[item_id]),
            {"quantity": 10},
            format="json",
        )
        self.assertEqual(update_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_to_basket_accumulates_quantity(self) -> None:
        """Повторное добавление того же товара увеличивает количество."""
        self.authenticate()
        self.product_info.quantity = 10
        self.product_info.save(update_fields=["quantity"])

        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 3},
            format="json",
        )
        resp = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        self.assertIn(
            resp.status_code,
            [status.HTTP_200_OK, status.HTTP_201_CREATED],
        )
        self.assertEqual(resp.data["data"]["quantity"], 5)


class ConfirmReserveValidationTests(APITestCase):
    """Проверка что подтверждение заказа корректно резервирует остаток."""

    def _create_basket_with_item(self, quantity: int) -> tuple[Order, Contact]:
        contact = Contact.objects.create(
            user=self.user,
            city="Moscow",
            street="Tverskaya",
            house="1",
            phone="+70000000001",
        )
        order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=quantity,
            state="basket",
        )
        return order, contact

    def test_confirm_increases_reserved_quantity(self) -> None:
        """Подтверждение заказа увеличивает reserved_quantity."""
        self.authenticate()
        self.product_info.quantity = 10
        self.product_info.save(update_fields=["quantity"])

        order, contact = self._create_basket_with_item(3)

        resp = self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order.pk, "contact_id": contact.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        pi = ProductInfo.objects.get(pk=self.product_info.pk)
        self.assertEqual(pi.reserved_quantity, 3)
        self.assertEqual(pi.quantity, 10)

    def test_confirm_rejects_when_insufficient_stock(self) -> None:
        """Нельзя подтвердить заказ, если остатка недостаточно."""
        self.authenticate()
        self.product_info.quantity = 2
        self.product_info.reserved_quantity = 0
        self.product_info.save(update_fields=["quantity", "reserved_quantity"])

        order, contact = self._create_basket_with_item(5)

        resp = self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order.pk, "contact_id": contact.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_two_orders_cannot_exceed_total_stock(self) -> None:
        """Два заказа не могут в сумме зарезервировать больше, чем quantity.

        Первый заказ резервирует 3 из 5, второй пытается резервировать 4 —
        должен получить ошибку.
        """
        self.authenticate()
        self.product_info.quantity = 5
        self.product_info.save(update_fields=["quantity"])

        # Первый заказ — успешно
        contact1 = Contact.objects.create(
            user=self.user,
            city="Moscow",
            street="Tverskaya",
            house="1",
            phone="+70000000001",
        )
        order1 = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order1,
            product_info=self.product_info,
            quantity=3,
            state="basket",
        )
        resp1 = self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order1.pk, "contact_id": contact1.pk},
            format="json",
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Второй заказ — должен провалиться (3+4=7 > 5)
        contact2 = Contact.objects.create(
            user=self.user,
            city="SPb",
            street="Nevsky",
            house="2",
            phone="+70000000002",
        )
        order2 = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order2,
            product_info=self.product_info,
            quantity=4,
            state="basket",
        )
        resp2 = self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order2.pk, "contact_id": contact2.pk},
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

        # Проверяем что reserved_quantity не превышает quantity
        pi = ProductInfo.objects.get(pk=self.product_info.pk)
        self.assertLessEqual(pi.reserved_quantity, pi.quantity)
        self.assertEqual(pi.reserved_quantity, 3)

    def test_cancel_order_releases_reserved_quantity(self) -> None:
        """Отмена заказа освобождает зарезервированное количество."""
        self.authenticate()
        self.product_info.quantity = 10
        self.product_info.save(update_fields=["quantity"])

        contact = Contact.objects.create(
            user=self.user,
            city="Moscow",
            street="Tverskaya",
            house="1",
            phone="+70000000001",
        )
        order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=5,
            state="basket",
        )

        # Подтверждаем
        self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order.pk, "contact_id": contact.pk},
            format="json",
        )
        pi = ProductInfo.objects.get(pk=self.product_info.pk)
        self.assertEqual(pi.reserved_quantity, 5)

        # Отменяем
        self.api_client.post(
            reverse("order-cancel", args=[order.pk]),
            format="json",
        )
        pi.refresh_from_db()
        self.assertEqual(pi.reserved_quantity, 0)

    def test_order_state_updates_on_item_cancellation(self) -> None:
        """При отмене всех позиций заказ переходит в canceled."""
        self.authenticate()
        self.product_info.quantity = 10
        self.product_info.save(update_fields=["quantity"])

        contact = Contact.objects.create(
            user=self.user,
            city="Moscow",
            street="Tverskaya",
            house="1",
            phone="+70000000001",
        )
        order = Order.objects.create(user=self.user, state="basket")
        OrderItem.objects.create(
            order=order,
            product_info=self.product_info,
            quantity=2,
            state="basket",
        )

        # Подтверждаем
        self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order.pk, "contact_id": contact.pk},
            format="json",
        )
        order.refresh_from_db()
        self.assertEqual(order.state, "confirmed")

        # Отменяем
        self.api_client.post(
            reverse("order-cancel", args=[order.pk]),
            format="json",
        )
        order.refresh_from_db()
        self.assertEqual(order.state, "canceled")
