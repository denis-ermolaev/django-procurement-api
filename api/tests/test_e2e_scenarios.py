"""E2E-тесты: полные пользовательские сценарии.

Каждый тест — это full user journey через API, который моделирует
реальное поведение пользователя от начала до конца.
"""

from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from api.models import Contact, Order, OrderItem, Shop, User
from api.tests.base import APITestCase


def _create_contact(client) -> int:
    """Создать тестовый контакт и вернуть его ID."""
    resp = client.post(
        reverse("contacts"),
        {
            "city": "Калининград",
            "street": "Ленина",
            "house": "1",
            "phone": "+70000000001",
        },
        format="json",
    )
    return resp.data["data"]["id"]


def _ship_order_via_shop(api_client, shop_user, order_id) -> None:
    """Провести заказ через цепочку статусов: accepted → assembled → sent.
    Используется для тестов, где нужно, чтобы заказ был отправлен."""
    api_client.force_authenticate(user=shop_user)
    items = OrderItem.objects.filter(order_id=order_id).order_by("id")
    for state in ("accepted", "assembled", "sent"):
        for item in items:
            resp = api_client.patch(
                reverse("shop-order-item-detail", args=[item.pk]),
                {"state": state},
                format="json",
            )
            assert resp.status_code == status.HTTP_200_OK, (
                f"Failed to transition item {item.pk} to {state}: {resp.data}"
            )


# ============================================================================ #
#                        СЦЕНАРИЙ 1: ПОЛНЫЙ ПУТЬ ПОКУПАТЕЛЯ                     #
# ============================================================================ #


class BuyerHappyPathTests(APITestCase):
    """Сценарий 1: Покупатель регистрируется, смотрит каталог,
    добавляет товары в корзину, создаёт контакт, подтверждает заказ,
    проверяет детали, отменяет и смотрит историю."""

    def test_01_buyer_journey(self) -> None:
        """1.1 Регистрация → JWT → каталог → корзина."""
        # 1. Регистрация
        response = self.api_client.post(
            "/api/auth/users/",
            {
                "first_name": "Иван",
                "last_name": "Покупателев",
                "email": "ivan@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)
        buyer = User.objects.get(email="ivan@example.com")
        self.assertEqual(buyer.type, "buyer")
        self.assertFalse(buyer.is_active)

        # Активируем пользователя (в тестах — напрямую)
        buyer.is_active = True
        buyer.save(update_fields=["is_active"])

        # 2. Получение JWT
        token_response = self.api_client.post(
            "/api/auth/jwt/create/",
            {"email": "ivan@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(token_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", token_response.data)
        self.assertIn("refresh", token_response.data)
        self.api_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}"
        )

        # 3. Просмотр каталога
        product_response = self.api_client.get(reverse("products"), {"page_size": 100})
        self.assertEqual(product_response.status_code, status.HTTP_200_OK)
        self.assertGreater(product_response.data["count"], 0)
        product_ids = [p["id"] for p in product_response.data["results"]]
        self.assertIn(self.product.pk, product_ids)

        # 4. Просмотр предложений
        offer_response = self.api_client.get(reverse("offers"), {"page_size": 100})
        self.assertEqual(offer_response.status_code, status.HTTP_200_OK)
        self.assertGreater(offer_response.data["count"], 0)
        offer_ids = [o["offer_id"] for o in offer_response.data["results"]]
        self.assertIn(self.product_info.pk, offer_ids)

        # 5. Детальная карточка предложения
        detail_response = self.api_client.get(
            reverse("offer-detail", args=[self.product_info.pk])
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["offer_id"], self.product_info.pk)
        self.assertEqual(detail_response.data["product_name"], self.product.name)
        self.assertEqual(detail_response.data["offer_name"], self.product_info.name)
        self.assertEqual(detail_response.data["shop_name"], self.shop.name)
        self.assertIn("available_quantity", detail_response.data)
        self.assertIn("parameters", detail_response.data)
        self.assertTrue(detail_response.data["can_add_to_basket"])

        # 6. Добавление товара в корзину
        add_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(add_response.data["data"]["offer_id"], self.product_info.pk)
        self.assertEqual(add_response.data["data"]["quantity"], 2)
        self.assertEqual(
            add_response.data["data"]["line_total"],
            2 * self.product_info.price,
        )
        self.assertEqual(add_response.data["data"]["warnings"], [])

        # 7. Проверка корзины
        basket_response = self.api_client.get(reverse("basket"))
        self.assertEqual(basket_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(basket_response.data["id"])
        self.assertEqual(basket_response.data["state"], "basket")
        self.assertEqual(len(basket_response.data["items"]), 1)
        self.assertEqual(
            basket_response.data["items"][0]["offer_id"],
            self.product_info.pk,
        )
        self.assertEqual(basket_response.data["items"][0]["quantity"], 2)
        self.assertEqual(basket_response.data["items"][0]["warnings"], [])
        self.assertTrue(basket_response.data["items"][0]["is_available"])
        self.assertEqual(basket_response.data["total"], 2 * self.product_info.price)

    def test_02_confirm_order_journey(self) -> None:
        """1.2 Контакт → подтверждение заказа → проверка деталей."""
        self.authenticate()

        # 1. Создаём контакт
        contact_id = _create_contact(self.api_client)

        # 2. Проверяем список контактов
        list_response = self.api_client.get(reverse("contacts"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["data"]), 1)
        self.assertEqual(list_response.data["data"][0]["city"], "Калининград")

        # 3. Добавляем товар в корзину
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 3},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        # 4. Подтверждаем заказ
        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm_response.data["state"], "confirmed")
        self.assertEqual(
            confirm_response.data["total_sum"],
            3 * self.product_info.price,
        )

        # 5. Проверяем детали заказа
        detail_response = self.api_client.get(
            reverse("order-detail", args=[order_id]),
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], order_id)
        self.assertEqual(detail_response.data["state"], "confirmed")
        self.assertEqual(detail_response.data["contact"], contact_id)
        self.assertIsNotNone(detail_response.data["confirmed_at"])
        self.assertEqual(len(detail_response.data["items"]), 1)
        item = detail_response.data["items"][0]
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(item["unit_price"], self.product_info.price)
        self.assertEqual(item["product_name_snapshot"], self.product.name)
        self.assertEqual(item["offer_name_snapshot"], self.product_info.name)
        self.assertEqual(item["shop_name_snapshot"], self.shop.name)
        self.assertEqual(
            detail_response.data["total_sum"],
            3 * self.product_info.price,
        )

        # 6. Корзина пуста после подтверждения
        basket_response = self.api_client.get(reverse("basket"))
        self.assertEqual(len(basket_response.data["items"]), 0)

        # 7. Товар зарезервирован
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 3)

    def test_03_cancel_and_history_journey(self) -> None:
        """1.3 Отмена заказа → история → товар снова доступен."""
        self.authenticate()

        # Создаём контакт, корзину и подтверждаем заказ
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.product_info.refresh_from_db()
        self.assertGreater(self.product_info.reserved_quantity, 0)

        # 1. Отмена заказа
        cancel_response = self.api_client.post(
            reverse("order-cancel", args=[order_id]),
            format="json",
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data["state"], "canceled")

        # 2. Детали заказа после отмены
        detail_response = self.api_client.get(
            reverse("order-detail", args=[order_id]),
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["state"], "canceled")

        # 3. Резерв освобождён
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 0)

        # 4. История заказов (исключает basket)
        history_response = self.api_client.get(reverse("orders"))
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.data["count"], 1)
        self.assertEqual(history_response.data["results"][0]["id"], order_id)
        self.assertEqual(history_response.data["results"][0]["state"], "canceled")
        self.assertEqual(history_response.data["results"][0]["total_sum"], 200)

        # 5. Товар снова доступен в каталоге
        product_response = self.api_client.get(reverse("products"), {"page_size": 100})
        product_ids = [p["id"] for p in product_response.data["results"]]
        self.assertIn(self.product.pk, product_ids)


# ============================================================================ #
#                          СЦЕНАРИЙ 2: НЕГАТИВНЫЙ ПУТЬ                          #
# ============================================================================ #


class BuyerNegativePathTests(APITestCase):
    """Сценарий 2: Негативные сценарии покупателя."""

    def test_01_exceed_stock(self) -> None:
        """2.1 Попытка добавить больше, чем есть на складе."""
        self.authenticate()

        # Пытаемся добавить больше, чем есть
        too_many_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 999},
            format="json",
        )
        self.assertEqual(too_many_response.status_code, status.HTTP_400_BAD_REQUEST)

        # Добавляем допустимое количество
        ok_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 5},
            format="json",
        )
        self.assertEqual(ok_response.status_code, status.HTTP_201_CREATED)

        # Повторно добавляем тот же товар — суммарно превышаем остаток
        overflow_response = self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 10},
            format="json",
        )
        self.assertEqual(overflow_response.status_code, status.HTTP_400_BAD_REQUEST)

        # Итоговое количество в корзине — 5
        item = OrderItem.objects.get(
            product_info=self.product_info,
            order__user=self.user,
            order__state="basket",
        )
        self.assertEqual(item.quantity, 5)

    def test_02_inactive_offer_in_basket(self) -> None:
        """2.2 Корзина с неактивным предложением — warning + reject confirm."""
        self.authenticate()

        # Добавляем товар
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        # Администратор скрывает предложение
        admin_user = User.objects.create_user(
            email="admin-e2e@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.api_client.force_authenticate(user=admin_user)
        self.api_client.patch(
            reverse("admin-offer-detail", args=[self.product_info.pk]),
            {"status": "hidden"},
            format="json",
        )

        # Возвращаемся к покупателю
        self.authenticate()

        # В корзине warning
        basket_response = self.api_client.get(reverse("basket"))
        self.assertEqual(basket_response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "Предложение больше недоступно.",
            basket_response.data["items"][0]["warnings"],
        )
        self.assertFalse(basket_response.data["items"][0]["is_available"])

        # Попытка подтвердить заказ
        contact_id = _create_contact(self.api_client)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_03_inactive_shop_confirm(self) -> None:
        """2.3 Подтверждение заказа с неактивным магазином."""
        self.authenticate()

        # Добавляем товар и контакт
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        # Администратор блокирует магазин
        admin_user = User.objects.create_user(
            email="admin-e2e-2@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.api_client.force_authenticate(user=admin_user)
        self.api_client.post(
            reverse("admin-shop-block", args=[self.shop.pk]),
            format="json",
        )

        # Возвращаемся к покупателю
        self.authenticate()

        # В корзине warning
        basket_response = self.api_client.get(reverse("basket"))
        self.assertIn(
            "Магазин не принимает новые заказы.",
            basket_response.data["items"][0]["warnings"],
        )

        # Попытка подтвердить заказ
        contact_id = _create_contact(self.api_client)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_04_foreign_data_access(self) -> None:
        """2.4 Попытка взаимодействия с чужими данными."""
        # Пользователь A создаёт корзину
        user_a = self.user
        self.authenticate(user_a)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket_response = self.api_client.get(reverse("basket"))
        item_id = basket_response.data["items"][0]["id"]
        order_id = basket_response.data["id"]

        # Пользователь B — чужие данные недоступны
        user_b = self.other_user
        self.authenticate(user_b)

        # Чужая корзина — пусто
        foreign_basket = self.api_client.get(reverse("basket"))
        self.assertEqual(len(foreign_basket.data["items"]), 0)

        # Изменение чужого item — 404
        patch_response = self.api_client.patch(
            reverse("basket-item-detail", args=[item_id]),
            {"quantity": 5},
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_404_NOT_FOUND)

        # Удаление чужого item — 404
        delete_response = self.api_client.delete(
            reverse("basket-item-detail", args=[item_id]),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

        # Подтверждение чужого заказа — 404
        contact_b_id = _create_contact(self.api_client)
        confirm_response = self.api_client.post(
            reverse("order-confirm"),
            {"order_id": order_id, "contact_id": contact_b_id},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_404_NOT_FOUND)

        # Отмена чужого заказа — предварительно подтвердим заказ user_a
        self.authenticate(user_a)
        contact_a_id = _create_contact(self.api_client)
        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_a_id},
                format="json",
            )

        # user_b пытается отменить — 404
        self.authenticate(user_b)
        cancel_response = self.api_client.post(
            reverse("order-cancel", args=[order_id]),
            format="json",
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_05_cancel_shipped_order(self) -> None:
        """2.5 Покупатель не может отменить отправленный заказ."""
        self.authenticate()

        # Создаём контакт, корзину и подтверждаем
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 1},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        # Магазин отправляет заказ (accepted → assembled → sent)
        shop_user = User.objects.create_user(
            email="shop-e2e-5@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.save(update_fields=["owner"])
        _ship_order_via_shop(self.api_client, shop_user, order_id)

        # Проверяем, что заказ действительно отправлен
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.state, "sent")

        # Покупатель пытается отменить
        self.authenticate()
        cancel_response = self.api_client.post(
            reverse("order-cancel", args=[order_id]),
            format="json",
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_06_confirm_empty_basket(self) -> None:
        """2.6 Подтверждение пустой корзины."""
        self.authenticate()

        # Создаём пустую корзину (без items)
        Order.objects.filter(user=self.user, state="basket").delete()
        basket = Order.objects.create(user=self.user, state="basket")
        contact_id = _create_contact(self.api_client)

        with self.captureOnCommitCallbacks(execute=True):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": basket.pk, "contact_id": contact_id},
                format="json",
            )
        self.assertEqual(confirm_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_07_total_stock_not_exceeded(self) -> None:
        """2.7 Два покупателя не могут превысить общий остаток."""
        buyer_b = User.objects.create_user(
            email="buyer-b@example.com",
            password="test-password",
            is_active=True,
        )

        self.product_info.quantity = 5
        self.product_info.reserved_quantity = 0
        self.product_info.save(update_fields=["quantity", "reserved_quantity"])

        # Покупатель A добавляет 3
        self.authenticate()
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 3},
            format="json",
        )
        basket_a = self.api_client.get(reverse("basket"))
        order_id_a = basket_a.data["id"]

        # Покупатель B добавляет 3 (можно, reservation ещё нет)
        self.api_client.force_authenticate(user=buyer_b)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 3},
            format="json",
        )
        basket_b = self.api_client.get(reverse("basket"))
        order_id_b = basket_b.data["id"]

        # Покупатель A подтверждает — успех (reserved=3)
        self.authenticate()
        contact_a_id = _create_contact(self.api_client)
        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            confirm_a = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id_a, "contact_id": contact_a_id},
                format="json",
            )
        self.assertEqual(confirm_a.status_code, status.HTTP_200_OK)

        # Покупатель B пытается подтвердить — ошибка
        self.api_client.force_authenticate(user=buyer_b)
        contact_b_id = _create_contact(self.api_client)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_b = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id_b, "contact_id": contact_b_id},
                format="json",
            )
        self.assertEqual(confirm_b.status_code, status.HTTP_400_BAD_REQUEST)

        # Проверяем, что остаток не превышен
        self.product_info.refresh_from_db()
        self.assertLessEqual(
            self.product_info.reserved_quantity,
            self.product_info.quantity,
        )
        self.assertEqual(self.product_info.reserved_quantity, 3)


# ============================================================================ #
#                       СЦЕНАРИЙ 3: ПОЛНЫЙ ПУТЬ МАГАЗИНА                        #
# ============================================================================ #


class ShopHappyPathTests(APITestCase):
    """Сценарий 3: Регистрация магазина → одобрение → управление офферами → обработка заказов."""

    def test_01_shop_registration_pending(self) -> None:
        """3.1 Магазин регистрируется и ждёт одобрения."""
        response = self.api_client.post(
            reverse("shop-register"),
            {
                "first_name": "Магазин",
                "last_name": "Владелец",
                "email": "shop-new@example.com",
                "password": "StrongPass123!",
                "shop_name": "Новый магазин",
                "url": "https://new-shop.example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["type"], "shop")
        self.assertEqual(response.data["shop"]["status"], "pending")

        user = User.objects.get(email="shop-new@example.com")
        shop = Shop.objects.get(owner=user)
        self.assertEqual(user.type, "shop")
        self.assertFalse(user.is_active)
        self.assertEqual(shop.status, "pending")

        # Попытка получить JWT — 401 (неактивный)
        token_response = self.api_client.post(
            "/api/auth/jwt/create/",
            {"email": "shop-new@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(token_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_02_shop_approved_and_creates_offers(self) -> None:
        """3.2 Админ одобряет → магазин создаёт предложения → товары в каталоге."""
        shop_user = User.objects.create_user(
            email="seller@example.com",
            password="test-password",
            first_name="Продавец",
            type="shop",
            is_active=True,
        )
        shop = Shop.objects.create(
            owner=shop_user,
            name="Тестовый магазин",
            url="https://test-shop.example.com",
            status="pending",
        )
        admin_user = User.objects.create_user(
            email="admin-shop@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )

        # Админ одобряет магазин
        self.api_client.force_authenticate(user=admin_user)
        approve_response = self.api_client.post(
            reverse("admin-shop-approve", args=[shop.pk]),
            format="json",
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_response.data["status"], "active")

        # Магазин обновляет профиль
        self.api_client.force_authenticate(user=shop_user)
        profile_response = self.api_client.patch(
            reverse("shop-profile"),
            {"name": "Обновлённый магазин", "url": "https://updated.example.com"},
            format="json",
        )
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data["name"], "Обновлённый магазин")

        # Админ создаёт категорию и товар
        self.api_client.force_authenticate(user=admin_user)
        cat_response = self.api_client.post(
            reverse("admin-categories"),
            {"name": "Электроника", "status": "active"},
            format="json",
        )
        category_id = cat_response.data["id"]
        prod_response = self.api_client.post(
            reverse("admin-products"),
            {"name": "Смартфон", "category": category_id, "status": "active"},
            format="json",
        )
        product_id = prod_response.data["id"]

        # Магазин создаёт предложение
        self.api_client.force_authenticate(user=shop_user)
        offer_response = self.api_client.post(
            reverse("shop-offers"),
            {
                "product": product_id,
                "name": "Смартфон 128GB",
                "quantity": 10,
                "price": 25000,
                "price_rrc": 29990,
            },
            format="json",
        )
        self.assertEqual(offer_response.status_code, status.HTTP_201_CREATED)

        # Покупатель видит товары в каталоге
        buyer = User.objects.create_user(
            email="buyer-catalog@example.com", password="test-password", is_active=True
        )
        self.api_client.force_authenticate(user=buyer)
        products_response = self.api_client.get(reverse("products"), {"page_size": 100})
        product_names = [p["name"] for p in products_response.data["results"]]
        self.assertIn("Смартфон", product_names)

    def test_03_shop_creates_and_updates_offer(self) -> None:
        """3.3 Магазин создаёт и обновляет предложение вручную."""
        shop_user = User.objects.create_user(
            email="seller-offer@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])

        self.api_client.force_authenticate(user=shop_user)

        # Создаём предложение
        create_response = self.api_client.post(
            reverse("shop-offers"),
            {
                "product": self.product.pk,
                "name": "Премиум-предложение",
                "quantity": 20,
                "price": 15000,
                "price_rrc": 19990,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        offer_id = create_response.data["id"]

        # Обновляем цену и статус
        update_response = self.api_client.patch(
            reverse("shop-offer-detail", args=[offer_id]),
            {"price": 14000, "status": "hidden"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["price"], 14000)
        self.assertEqual(update_response.data["status"], "hidden")

        # Покупатель не видит скрытое предложение
        self.authenticate()
        offer_detail = self.api_client.get(
            reverse("offer-detail", args=[offer_id]),
        )
        self.assertEqual(offer_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_04_shop_processes_order(self) -> None:
        """3.4 Магазин обрабатывает заказ покупателя."""
        shop_user = User.objects.create_user(
            email="seller-process@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])
        original_quantity = self.product_info.quantity

        # Покупатель: корзина → контакт → подтверждение
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            confirm_response = self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        # Магазин видит новые позиции
        self.api_client.force_authenticate(user=shop_user)
        items_response = self.api_client.get(reverse("shop-order-items"))
        self.assertEqual(items_response.status_code, status.HTTP_200_OK)
        self.assertGreater(items_response.data["count"], 0)
        item_id = items_response.data["results"][0]["id"]

        # Магазин проводит цепочку: accepted → assembled → sent
        for state in ("accepted", "assembled", "sent"):
            resp = self.api_client.patch(
                reverse("shop-order-item-detail", args=[item_id]),
                {"state": state},
                format="json",
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertEqual(resp.data["state"], state)

        # Остаток списан после отправки
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.quantity, original_quantity - 2)
        self.assertEqual(self.product_info.reserved_quantity, 0)

        # Покупатель видит статус "sent"
        self.authenticate()
        detail_response = self.api_client.get(
            reverse("order-detail", args=[order_id]),
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["state"], "sent")


# ============================================================================ #
#                      СЦЕНАРИЙ 4: НЕГАТИВНЫЕ СЦЕНАРИИ МАГАЗИНА                 #
# ============================================================================ #


class ShopNegativePathTests(APITestCase):
    """Сценарий 4: Негативные сценарии магазина."""

    def test_01_pending_shop_cannot_create_offer(self) -> None:
        """4.1 Магазин с pending статусом не может создать предложение."""
        shop_user = User.objects.create_user(
            email="pending-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        Shop.objects.create(owner=shop_user, name="Pending shop", status="pending")
        self.api_client.force_authenticate(user=shop_user)

        response = self.api_client.post(
            reverse("shop-offers"),
            {
                "product": self.product.pk,
                "name": "Test",
                "quantity": 1,
                "price": 100,
                "price_rrc": 120,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_02_shop_cannot_edit_foreign_offer(self) -> None:
        """4.2 Магазин не может редактировать чужие предложения (404)."""
        shop_a = User.objects.create_user(
            email="shop-a@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        shop_b = User.objects.create_user(
            email="shop-b@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_a
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])

        # Даём shop_b активный магазин (чтобы пройти IsActiveShop)
        Shop.objects.create(owner=shop_b, name="Shop B", status="active")

        self.api_client.force_authenticate(user=shop_b)
        response = self.api_client.patch(
            reverse("shop-offer-detail", args=[self.product_info.pk]),
            {"price": 95},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_03_shop_cancels_item_releases_reserve(self) -> None:
        """4.3 Магазин отменяет позицию — резерв освобождается, заказ отменяется."""
        shop_user = User.objects.create_user(
            email="shop-cancel@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])

        # Покупатель создаёт и подтверждает заказ
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 2)

        # Магазин отменяет позицию
        self.api_client.force_authenticate(user=shop_user)
        item = OrderItem.objects.get(order_id=order_id)
        cancel_response = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item.pk]),
            {"state": "canceled"},
            format="json",
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)

        # Резерв освобождён
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 0)

        # Заказ перешёл в "canceled"
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.state, "canceled")

    def test_04_blocked_shop_limitations(self) -> None:
        """4.4 Blocked shop: не может создать offer, но может обработать заказ."""
        shop_user = User.objects.create_user(
            email="blocked-shop@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])

        # Покупатель создаёт заказ
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 1},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {
                    "order_id": basket.data["id"],
                    "contact_id": contact_id,
                },
                format="json",
            )

        # Админ блокирует магазин
        admin_user = User.objects.create_user(
            email="admin-block@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.api_client.force_authenticate(user=admin_user)
        self.api_client.post(
            reverse("admin-shop-block", args=[self.shop.pk]),
            format="json",
        )

        # Магазин не может создать предложение
        self.api_client.force_authenticate(user=shop_user)
        create_response = self.api_client.post(
            reverse("shop-offers"),
            {
                "product": self.product.pk,
                "name": "Blocked offer",
                "quantity": 1,
                "price": 100,
                "price_rrc": 120,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

        # Но может обработать существующий заказ
        item = OrderItem.objects.filter(product_info__shop=self.shop).first()
        assert item is not None, "Expected an order item for this shop"
        accept_response = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item.pk]),
            {"state": "accepted"},
            format="json",
        )
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)


# ============================================================================ #
#                     СЦЕНАРИЙ 5: ПОЛНЫЙ ПУТЬ АДМИНИСТРАТОРА                     #
# ============================================================================ #


class AdminHappyPathTests(APITestCase):
    """Сценарий 5: Администратор управляет магазинами, каталогом, заказами."""

    def setUp(self) -> None:
        super().setUp()
        self.admin_user = User.objects.create_user(
            email="admin-path@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )

    def test_01_admin_manages_shops(self) -> None:
        """5.1 Администратор одобряет, блокирует и обновляет магазин."""
        self.api_client.force_authenticate(user=self.admin_user)

        # Одобряем
        approve = self.api_client.post(
            reverse("admin-shop-approve", args=[self.shop.pk]),
            format="json",
        )
        self.assertEqual(approve.status_code, status.HTTP_200_OK)
        self.assertEqual(approve.data["status"], "active")

        # Блокируем
        block = self.api_client.post(
            reverse("admin-shop-block", args=[self.shop.pk]),
            format="json",
        )
        self.assertEqual(block.status_code, status.HTTP_200_OK)
        self.assertEqual(block.data["status"], "blocked")
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.status, "blocked")

        # Обновляем через PATCH
        update = self.api_client.patch(
            reverse("admin-shop-detail", args=[self.shop.pk]),
            {"is_accepting_orders": False, "name": "Обновлённый"},
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data["is_accepting_orders"], False)
        self.assertEqual(update.data["name"], "Обновлённый")

    def test_02_admin_manages_catalog(self) -> None:
        """5.2 Администратор управляет каталогом и блокирует предложения."""
        self.api_client.force_authenticate(user=self.admin_user)

        # Создаёт категорию
        cat = self.api_client.post(
            reverse("admin-categories"),
            {"name": "Аксессуары", "status": "active"},
            format="json",
        )
        self.assertEqual(cat.status_code, status.HTTP_201_CREATED)

        # Создаёт товар
        prod = self.api_client.post(
            reverse("admin-products"),
            {"name": "Чехол", "category": cat.data["id"], "status": "active"},
            format="json",
        )
        self.assertEqual(prod.status_code, status.HTTP_201_CREATED)

        # Создаёт параметр
        param = self.api_client.post(
            reverse("admin-parameters"),
            {"name": "материал"},
            format="json",
        )
        self.assertEqual(param.status_code, status.HTTP_201_CREATED)

        # Блокирует предложение
        blocked = self.api_client.patch(
            reverse("admin-offer-detail", args=[self.product_info.pk]),
            {"status": "blocked"},
            format="json",
        )
        self.assertEqual(blocked.status_code, status.HTTP_200_OK)
        self.assertEqual(blocked.data["status"], "blocked")

        # Покупатель не видит заблокированное предложение
        self.authenticate()
        offer_detail = self.api_client.get(
            reverse("offer-detail", args=[self.product_info.pk]),
        )
        self.assertEqual(offer_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_03_admin_cancels_order_with_reason(self) -> None:
        """5.3 Администратор отменяет заказ с причиной — резерв освобождён."""
        # Покупатель создаёт и подтверждает заказ
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 2)

        # Админ отменяет с причиной
        self.api_client.force_authenticate(user=self.admin_user)
        cancel = self.api_client.patch(
            reverse("admin-order-detail", args=[order_id]),
            {"state": "canceled", "cancellation_reason": "Ошибочный заказ"},
            format="json",
        )
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel.data["state"], "canceled")
        self.assertEqual(cancel.data["cancellation_reason"], "Ошибочный заказ")

        # Резерв освобождён
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 0)

    def test_04_admin_sets_processing_status(self) -> None:
        """5.4 Администратор меняет статус заказа на processing."""
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 1},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )

        # Админ устанавливает processing
        self.api_client.force_authenticate(user=self.admin_user)
        response = self.api_client.patch(
            reverse("admin-order-detail", args=[order_id]),
            {"state": "processing"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["state"], "processing")

        # Позиции заказа не изменились
        self.assertEqual(response.data["items"][0]["state"], "confirmed")


# ============================================================================ #
#                    СЦЕНАРИЙ 6: STATE MACHINE ЧЕРЕЗ API                         #
# ============================================================================ #


class OrderStateMachineTests(APITestCase):
    """Сценарий 6: Проверка полного потока статусов."""

    def setUp(self) -> None:
        super().setUp()
        self.shop_user = User.objects.create_user(
            email="shop-sm@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = self.shop_user
        self.shop.status = "active"
        self.shop.save(update_fields=["owner", "status"])

        self.admin_user = User.objects.create_user(
            email="admin-sm@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )

    def _create_confirmed_order(self) -> tuple[int, int]:
        """Создать подтверждённый заказ. Возвращает (order_id, item_id)."""
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 1},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]
        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        item = OrderItem.objects.get(order_id=order_id)
        return order_id, item.pk

    def test_01_full_status_flow(self) -> None:
        """6.1 Полный поток: confirmed→accepted→assembled→sent→delivered."""
        order_id, item_id = self._create_confirmed_order()
        self.api_client.force_authenticate(user=self.shop_user)

        for new_state in ("accepted", "assembled", "sent"):
            resp = self.api_client.patch(
                reverse("shop-order-item-detail", args=[item_id]),
                {"state": new_state},
                format="json",
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            self.assertEqual(resp.data["state"], new_state)

        # delivered может только админ
        self.api_client.force_authenticate(user=self.admin_user)
        delivered = self.api_client.patch(
            reverse("admin-order-item-detail", args=[item_id]),
            {"state": "delivered"},
            format="json",
        )
        self.assertEqual(delivered.status_code, status.HTTP_200_OK)
        self.assertEqual(delivered.data["state"], "delivered")

    def test_02_partial_cancel_then_full_cancel(self) -> None:
        """6.2 Частичная отмена → partially_canceled → полная отмена."""
        # Создаём заказ с двумя разными позициями
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.other_product_info.pk, "quantity": 1},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )

        items = list(OrderItem.objects.filter(order_id=order_id).order_by("id"))
        self.assertEqual(len(items), 2)

        # Магазин отменяет одну позицию
        self.api_client.force_authenticate(user=self.shop_user)
        self.api_client.patch(
            reverse("shop-order-item-detail", args=[items[0].pk]),
            {"state": "canceled"},
            format="json",
        )
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.state, "partially_canceled")

        # Покупатель отменяет оставшуюся
        self.authenticate()
        cancel = self.api_client.post(
            reverse("order-cancel", args=[order_id]),
            format="json",
        )
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.state, "canceled")

        # Все позиции canceled
        for item in OrderItem.objects.filter(order_id=order_id):
            self.assertEqual(item.state, "canceled")

    def test_03_admin_can_skip_states_shop_cannot(self) -> None:
        """6.3 Админ может перепрыгивать статусы, магазин — нет."""
        order_id, item_id = self._create_confirmed_order()

        # Магазин не может confirmed→delivered
        self.api_client.force_authenticate(user=self.shop_user)
        shop_resp = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item_id]),
            {"state": "delivered"},
            format="json",
        )
        self.assertEqual(shop_resp.status_code, status.HTTP_400_BAD_REQUEST)

        # Админ может confirmed→delivered
        self.api_client.force_authenticate(user=self.admin_user)
        admin_resp = self.api_client.patch(
            reverse("admin-order-item-detail", args=[item_id]),
            {"state": "delivered"},
            format="json",
        )
        self.assertEqual(admin_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_resp.data["state"], "delivered")

    def test_04_invalid_transitions(self) -> None:
        """6.4 Невалидные переходы статусов для магазина."""
        order_id, item_id = self._create_confirmed_order()
        self.api_client.force_authenticate(user=self.shop_user)

        # Проводим позицию через все статусы до sent
        for state in ("accepted", "assembled", "sent"):
            resp = self.api_client.patch(
                reverse("shop-order-item-detail", args=[item_id]),
                {"state": state},
                format="json",
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Попытка откатить sent→assembled — невалидно
        rollback = self.api_client.patch(
            reverse("shop-order-item-detail", args=[item_id]),
            {"state": "assembled"},
            format="json",
        )
        self.assertEqual(rollback.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================ #
#                        СЦЕНАРИЙ 7: ФИЛЬТРАЦИЯ И ПОИСК                          #
# ============================================================================ #


class CatalogFilterTests(APITestCase):
    """Сценарий 7: Фильтрация каталога по различным критериям."""

    def test_01_product_filters(self) -> None:
        """7.1 Фильтрация каталога: поиск, категория, магазин, цена, параметр."""
        self.authenticate()

        # Поиск
        resp = self.api_client.get(reverse("products"), {"search": "phone"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

        # Категория
        resp = self.api_client.get(
            reverse("products"), {"category_id": self.category.pk}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

        # Магазин
        resp = self.api_client.get(reverse("products"), {"shop_id": self.shop.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

        # Цена
        resp = self.api_client.get(
            reverse("products"),
            {"price_min": 90, "price_max": 110},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

        # Параметр
        resp = self.api_client.get(
            reverse("products"),
            {"parameter": "color:black"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)

    def test_02_offer_filters(self) -> None:
        """7.2 Фильтрация предложений: in_stock, ordering, combined."""
        self.authenticate()

        # in_stock
        resp = self.api_client.get(
            reverse("offers"), {"in_stock": "true", "page_size": 100}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(resp.data["count"], 0)

        # ordering по цене
        resp = self.api_client.get(
            reverse("offers"), {"ordering": "price", "page_size": 100}
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        prices = [o["price"] for o in resp.data["results"]]
        self.assertEqual(prices, sorted(prices))

        # Комбинированный
        resp = self.api_client.get(
            reverse("offers"),
            {
                "category_id": self.other_category.pk,
                "price_max": 600,
                "in_stock": "true",
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(
            resp.data["results"][0]["offer_id"],
            self.other_product_info.pk,
        )

    def test_03_categories_active_only(self) -> None:
        """7.3 Категории только с активными предложениями."""
        self.authenticate()

        # Все активные категории
        resp = self.api_client.get(reverse("categories"))
        self.assertEqual(len(resp.data), 2)

        # Архивируем все предложения в одной категории
        admin = User.objects.create_user(
            email="admin-filter@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.api_client.force_authenticate(user=admin)
        self.api_client.patch(
            reverse("admin-offer-detail", args=[self.product_info.pk]),
            {"status": "archived"},
            format="json",
        )

        # Категория исчезла
        self.authenticate()
        resp = self.api_client.get(reverse("categories"))
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], self.other_category.name)


# ============================================================================ #
#                       СЦЕНАРИЙ 10: МЯГКОЕ УДАЛЕНИЕ КОНТАКТА                   #
# ============================================================================ #


class ContactSoftDeleteTests(APITestCase):
    """Сценарий 10: Мягкое удаление контакта."""

    def test_01_contact_bound_to_order_soft_deleted(self) -> None:
        """10.1 Контакт, привязанный к заказу, не удаляется физически."""
        self.authenticate()

        # Создаём контакт
        contact_id = _create_contact(self.api_client)

        # Создаём и подтверждаем заказ с этим контактом
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 1},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": basket.data["id"], "contact_id": contact_id},
                format="json",
            )

        # Удаляем контакт
        delete_response = self.api_client.delete(
            reverse("contact-detail", args=[contact_id]),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Контакт не удалён физически (is_deleted=True)
        contact = Contact.objects.get(pk=contact_id)
        self.assertTrue(contact.is_deleted)

        # Контакт недоступен через API
        get_response = self.api_client.get(
            reverse("contact-detail", args=[contact_id]),
        )
        self.assertEqual(get_response.status_code, status.HTTP_404_NOT_FOUND)

        # Заказ всё ещё ссылается на контакт
        orders = list(Order.objects.filter(user=self.user).exclude(state="basket"))
        if orders:
            self.assertEqual(getattr(orders[0], "contact_id"), contact_id)

    def test_02_contact_without_orders_physically_deleted(self) -> None:
        """10.2 Контакт без заказов удаляется физически."""
        self.authenticate()
        contact_id = _create_contact(self.api_client)

        # Удаляем
        delete_response = self.api_client.delete(
            reverse("contact-detail", args=[contact_id]),
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Контакт физически удалён
        self.assertFalse(Contact.objects.filter(pk=contact_id).exists())

        # Список контактов пуст
        list_resp = self.api_client.get(reverse("contacts"))
        self.assertEqual(len(list_resp.data["data"]), 0)


# ============================================================================ #
#                       СЦЕНАРИЙ 11: РЕГИСТРАЦИЯ И JWT                          #
# ============================================================================ #


class AuthFlowTests(APITestCase):
    """Сценарий 11: Полный цикл аутентификации."""

    def test_01_full_auth_cycle(self) -> None:
        """11.1 Регистрация → активация → JWT → профиль → refresh."""
        # Регистрация
        resp = self.api_client.post(
            "/api/auth/users/",
            {
                "first_name": "Тест",
                "last_name": "Юзер",
                "email": "testuser@example.com",
                "password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Активация (в тесте — напрямую)
        User.objects.filter(email="testuser@example.com").update(is_active=True)

        # JWT
        token = self.api_client.post(
            "/api/auth/jwt/create/",
            {"email": "testuser@example.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(token.status_code, status.HTTP_200_OK)
        access = token.data["access"]

        # Профиль
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        profile = self.api_client.get("/api/auth/users/me/")
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(profile.data["email"], "testuser@example.com")

        # Refresh
        refresh = self.api_client.post(
            "/api/auth/jwt/refresh/",
            {"refresh": token.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh.data)

    def test_02_regular_registration_cannot_set_shop_admin(self) -> None:
        """11.2 Обычная регистрация не может создать shop/admin."""
        for user_type in ("shop", "admin"):
            with self.subTest(user_type=user_type):
                resp = self.api_client.post(
                    "/api/auth/users/",
                    {
                        "first_name": "Wrong",
                        "last_name": "Role",
                        "email": f"{user_type}@example.com",
                        "password": "StrongPass123!",
                        "type": user_type,
                    },
                    format="json",
                )
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("type", resp.data)


# ============================================================================ #
#                     СЦЕНАРИЙ 12: АДМИН ОТМЕНА ЗАКАЗА                          #
# ============================================================================ #


class AdminOrderCancelTests(APITestCase):
    """Сценарий 12: Администратор отменяет заказ."""

    def test_01_admin_cancel_releases_reserve(self) -> None:
        """12.1 Админ отменяет заказ — резерв освобождается."""
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 2)

        # Админ отменяет
        admin = User.objects.create_user(
            email="admin-cancel@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.api_client.force_authenticate(user=admin)
        cancel = self.api_client.patch(
            reverse("admin-order-detail", args=[order_id]),
            {"state": "canceled", "cancellation_reason": "Возврат"},
            format="json",
        )
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel.data["state"], "canceled")
        self.assertEqual(cancel.data["cancellation_reason"], "Возврат")

        # Резерв освобождён
        self.product_info.refresh_from_db()
        self.assertEqual(self.product_info.reserved_quantity, 0)

    def test_02_admin_cannot_cancel_shipped_order(self) -> None:
        """12.2 Админ не может отменить заказ с отправленными позициями."""
        self.authenticate()
        contact_id = _create_contact(self.api_client)
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 1},
            format="json",
        )
        basket = self.api_client.get(reverse("basket"))
        order_id = basket.data["id"]

        with (
            patch("api.services.orders.send_order_confirmation_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.api_client.post(
                reverse("order-confirm"),
                {"order_id": order_id, "contact_id": contact_id},
                format="json",
            )

        # Магазин отправляет
        shop_user = User.objects.create_user(
            email="shop-ship@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.save(update_fields=["owner"])
        _ship_order_via_shop(self.api_client, shop_user, order_id)

        # Админ пытается отменить
        admin = User.objects.create_user(
            email="admin-fail@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )
        self.api_client.force_authenticate(user=admin)
        cancel = self.api_client.patch(
            reverse("admin-order-detail", args=[order_id]),
            {"state": "canceled", "cancellation_reason": "Ошибка"},
            format="json",
        )
        self.assertEqual(cancel.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================ #
#                      СЦЕНАРИЙ 14: ОЧИСТКА КОРЗИНЫ                             #
# ============================================================================ #


class BasketClearTests(APITestCase):
    """Сценарий 14: Очистка корзины."""

    def test_01_clear_basket_with_items(self) -> None:
        """14.1 Добавить товары → очистить корзину → корзина пуста."""
        self.authenticate()

        # Добавляем 2 разных товара
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.product_info.pk, "quantity": 2},
            format="json",
        )
        self.api_client.post(
            reverse("basket-items"),
            {"offer_id": self.other_product_info.pk, "quantity": 1},
            format="json",
        )

        # Проверяем, что в корзине 2 позиции
        basket = self.api_client.get(reverse("basket"))
        self.assertEqual(len(basket.data["items"]), 2)

        # Очищаем
        delete_resp = self.api_client.delete(reverse("basket"))
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Корзина пуста
        basket = self.api_client.get(reverse("basket"))
        self.assertEqual(len(basket.data["items"]), 0)

    def test_02_clear_empty_basket(self) -> None:
        """14.2 Очистить пустую корзину (нет Order basket) — 204 без ошибок."""
        self.authenticate()

        # Нет корзины — очистка не вызывает ошибок
        delete_resp = self.api_client.delete(reverse("basket"))
        self.assertEqual(delete_resp.status_code, status.HTTP_204_NO_CONTENT)


# ============================================================================ #
#                  СЦЕНАРИЙ 15: АДМИНИСТРИРОВАНИЕ ПОЛЬЗОВАТЕЛЕЙ                  #
# ============================================================================ #


class AdminUserManagementTests(APITestCase):
    """Сценарий 15: Администратор управляет пользователями."""

    def setUp(self) -> None:
        super().setUp()
        self.admin_user = User.objects.create_user(
            email="admin-mgmt@example.com",
            password="test-password",
            type="admin",
            is_staff=True,
            is_active=True,
        )

    def test_01_admin_activates_and_changes_role(self) -> None:
        """15.1 Админ активирует пользователя и меняет роль."""
        self.api_client.force_authenticate(user=self.admin_user)

        # Активируем (проверяем через БД, т.к. UserSerializer не содержит is_active)
        activate_resp = self.api_client.patch(
            reverse("admin-user-detail", args=[self.user.pk]),
            {"is_active": True},
            format="json",
        )
        self.assertEqual(activate_resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

        # Меняем роль на admin с is_staff
        role_change = self.api_client.patch(
            reverse("admin-user-detail", args=[self.user.pk]),
            {"type": "admin", "is_staff": True},
            format="json",
        )
        self.assertEqual(role_change.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.type, "admin")
        self.assertTrue(self.user.is_staff)

    def test_02_admin_role_invariants(self) -> None:
        """15.2 Нельзя назначить shop без магазина, admin без is_staff."""
        self.api_client.force_authenticate(user=self.admin_user)
        plain_user = User.objects.create_user(
            email="plain@example.com",
            password="test-password",
            is_active=True,
        )

        # shop без магазина — ошибка
        shop_without = self.api_client.patch(
            reverse("admin-user-detail", args=[plain_user.pk]),
            {"type": "shop"},
            format="json",
        )
        self.assertEqual(shop_without.status_code, status.HTTP_400_BAD_REQUEST)

        # admin без is_staff — ошибка
        admin_no_staff = self.api_client.patch(
            reverse("admin-user-detail", args=[plain_user.pk]),
            {"type": "admin"},
            format="json",
        )
        self.assertEqual(admin_no_staff.status_code, status.HTTP_400_BAD_REQUEST)

        # Нельзя сменить роль владельца магазина
        shop_user = User.objects.create_user(
            email="shop-owner@example.com",
            password="test-password",
            type="shop",
            is_active=True,
        )
        self.shop.owner = shop_user
        self.shop.save(update_fields=["owner"])
        cannot_change = self.api_client.patch(
            reverse("admin-user-detail", args=[shop_user.pk]),
            {"type": "buyer"},
            format="json",
        )
        self.assertEqual(cannot_change.status_code, status.HTTP_400_BAD_REQUEST)
