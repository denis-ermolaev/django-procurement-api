import logging
from functools import partial

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from api.management.email_service import send_order_confirmation
from api.models import Contact, Order, OrderItem, ProductInfo, Shop, User

logger = logging.getLogger(__name__)

SHOP_STATE_ORDER = ("confirmed", "accepted", "assembled", "sent", "delivered")


# 1. Общие операции со статусами и резервом ----
def recalculate_order_state(order: Order) -> Order:
    if order.state == "basket":
        return order

    item_states = list(
        OrderItem.objects.filter(order=order).values_list("state", flat=True)
    )
    if not item_states:
        return order

    non_canceled_states = [state for state in item_states if state != "canceled"]
    if not non_canceled_states:
        new_state = "canceled"
    elif any(state == "canceled" for state in item_states):
        new_state = "partially_canceled"
    elif all(state == "delivered" for state in non_canceled_states):
        new_state = "delivered"
    elif all(state in {"sent", "delivered"} for state in non_canceled_states):
        new_state = "sent"
    elif any(state in {"accepted", "assembled"} for state in non_canceled_states):
        new_state = "processing"
    else:
        new_state = "confirmed"

    if order.state != new_state:
        old_state = order.state
        order.state = new_state
        order.save(update_fields=["state", "updated_at"])
        logger.info(
            "[recalculate_order_state] order_state_recalculated order_id=%s old_state=%s new_state=%s",
            order.pk,
            old_state,
            new_state,
        )
    return order


def release_item_reserve(order_item: OrderItem) -> None:
    product_info = ProductInfo.objects.select_for_update().get(
        pk=order_item.product_info.pk
    )
    if product_info.reserved_quantity <= 0:
        return

    released_quantity = min(product_info.reserved_quantity, order_item.quantity)
    product_info.reserved_quantity -= released_quantity
    product_info.save(update_fields=["reserved_quantity"])
    logger.info(
        "[release_item_reserve] order_item_reserve_released order_id=%s item_id=%s product_info_id=%s quantity=%s",
        order_item.order.pk,
        order_item.pk,
        product_info.pk,
        released_quantity,
    )


def ship_item_stock(order_item: OrderItem) -> None:
    product_info = ProductInfo.objects.select_for_update().get(
        pk=order_item.product_info.pk
    )
    if product_info.reserved_quantity < order_item.quantity:
        raise ValidationError(
            {
                "state": "Нельзя отправить позицию: зарезервированного остатка недостаточно."
            }
        )
    if product_info.quantity < order_item.quantity:
        raise ValidationError(
            {"state": "Нельзя отправить позицию: физического остатка недостаточно."}
        )

    product_info.reserved_quantity -= order_item.quantity
    product_info.quantity -= order_item.quantity
    product_info.save(update_fields=["reserved_quantity", "quantity"])
    logger.info(
        "[ship_item_stock] order_item_stock_shipped order_id=%s item_id=%s product_info_id=%s quantity=%s",
        order_item.order.pk,
        order_item.pk,
        product_info.pk,
        order_item.quantity,
    )


def cancel_order_items(order: Order) -> None:
    for item in OrderItem.objects.select_for_update().filter(order=order):
        if item.state in {"sent", "delivered", "canceled"}:
            continue
        release_item_reserve(item)
        item.state = "canceled"
        item.save(update_fields=["state"])


def apply_order_item_snapshot(item: OrderItem, product_info: ProductInfo) -> None:
    item.unit_price = product_info.price
    item.price_rrc_snapshot = product_info.price_rrc
    item.product_name_snapshot = product_info.product.name
    item.offer_name_snapshot = product_info.name
    item.shop_name_snapshot = product_info.shop.name
    item.external_id_snapshot = product_info.external_id


def send_order_confirmation_after_commit(order_id: int) -> None:
    try:
        order = Order.objects.select_related("user").get(pk=order_id)
        send_order_confirmation(order)
    except Exception:
        logger.exception(
            "[send_order_confirmation_after_commit] order_confirm_email_failed order_id=%s",
            order_id,
        )


# 2. Покупательские операции ----
@transaction.atomic
def confirm_order(user: User, *, order_id: int, contact_id: int) -> Order:
    logger.debug(
        "[confirm_order] order_confirm_started user_id=%s order_id=%s contact_id=%s",
        user.pk,
        order_id,
        contact_id,
    )

    order = get_object_or_404(Order, id=order_id, user=user, state="basket")
    items = list(
        OrderItem.objects.select_for_update()
        .filter(order=order)
        .select_related("product_info__shop", "product_info__product__category")
        .order_by("id")
    )
    if not items:
        logger.warning(
            "[confirm_order] order_confirm_rejected_empty_basket user_id=%s order_id=%s",
            user.pk,
            order.pk,
        )
        raise ValidationError(
            {"order_id": "Нельзя подтвердить заказ без позиций в корзине."}
        )

    contact = get_object_or_404(Contact, id=contact_id, user=user, is_deleted=False)

    for item in items:
        product_info = (
            ProductInfo.objects.select_for_update()
            .select_related("shop", "product__category")
            .get(pk=item.product_info.pk)
        )
        available_quantity = product_info.quantity - product_info.reserved_quantity
        if (
            product_info.status != "active"
            or product_info.shop.status != "active"
            or not product_info.shop.is_accepting_orders
            or product_info.product.status != "active"
            or product_info.product.category.status != "active"
        ):
            raise ValidationError(
                {
                    "order_id": (
                        "Заказ содержит предложение, которое больше недоступно для продажи."
                    )
                }
            )
        if item.quantity > available_quantity:
            logger.warning(
                (
                    "[confirm_order] order_confirm_rejected_stock user_id=%s order_id=%s "
                    "item_id=%s product_info_id=%s requested_quantity=%s available_quantity=%s"
                ),
                user.pk,
                order.pk,
                item.pk,
                product_info.pk,
                item.quantity,
                available_quantity,
            )
            raise ValidationError(
                {
                    "order_id": (
                        "Недостаточно остатка для подтверждения заказа. "
                        f"Предложение {product_info.pk}: доступно {available_quantity}."
                    )
                }
            )

        product_info.reserved_quantity += item.quantity
        product_info.save(update_fields=["reserved_quantity"])
        item.state = "confirmed"
        apply_order_item_snapshot(item, product_info)
        item.save(
            update_fields=[
                "state",
                "unit_price",
                "price_rrc_snapshot",
                "product_name_snapshot",
                "offer_name_snapshot",
                "shop_name_snapshot",
                "external_id_snapshot",
            ]
        )

    order.state = "confirmed"
    order.contact = contact
    order.confirmed_at = timezone.now()
    order.save(update_fields=["state", "contact", "confirmed_at", "updated_at"])

    logger.info(
        "[confirm_order] order_confirmed user_id=%s order_id=%s contact_id=%s",
        user.pk,
        order.pk,
        contact.pk,
    )
    transaction.on_commit(partial(send_order_confirmation_after_commit, order.pk))
    return order


def get_order_history(user: User) -> QuerySet[Order]:
    orders = Order.objects.filter(user=user).exclude(state="basket").order_by("id")
    logger.debug(
        "[get_order_history] order_history_loaded user_id=%s order_count=%s",
        user.pk,
        orders.count(),
    )
    return orders


def get_user_order(user: User, pk: int) -> Order:
    order = get_object_or_404(Order, pk=pk, user=user)
    logger.debug(
        "[get_user_order] order_detail_loaded user_id=%s order_id=%s state=%s",
        user.pk,
        order.pk,
        order.state,
    )
    return order


@transaction.atomic
def cancel_order_by_buyer(order: Order) -> Order:
    if order.state not in {"confirmed", "partially_canceled"}:
        raise ValidationError(
            {"state": "Покупатель может отменить заказ только до начала обработки."}
        )
    if (
        OrderItem.objects.filter(order=order)
        .exclude(state__in=["confirmed", "canceled"])
        .exists()
    ):
        raise ValidationError(
            {"state": "Покупатель не может отменить заказ после начала обработки."}
        )

    cancel_order_items(order)
    order.state = "canceled"
    order.save(update_fields=["state", "updated_at"])
    logger.info(
        "[cancel_order_by_buyer] order_canceled_by_buyer user_id=%s order_id=%s",
        order.user.pk,
        order.pk,
    )
    return order


def update_order_state(order: Order, new_state: str) -> Order:
    if new_state != "canceled":
        raise ValidationError({"state": "Покупатель может только отменить заказ."})
    return cancel_order_by_buyer(order)


# 3. Операции магазина ----
def get_shop_order_items(user: User) -> QuerySet[OrderItem]:
    shop = get_object_or_404(Shop, owner=user)
    items = (
        OrderItem.objects.filter(product_info__shop=shop)
        .exclude(order__state="basket")
        .select_related("order", "product_info", "order__contact")
        .order_by("id")
    )
    logger.debug(
        "[get_shop_order_items] shop_order_items_loaded user_id=%s shop_id=%s item_count=%s",
        user.pk,
        shop.pk,
        items.count(),
    )
    return items


@transaction.atomic
def update_shop_order_item_state(
    user: User, *, item_id: int, new_state: str
) -> OrderItem:
    shop = get_object_or_404(Shop, owner=user)
    if shop.status != "active" or not shop.is_accepting_orders:
        raise ValidationError(
            {"shop": "Магазин должен быть активным и принимать заказы."}
        )
    item = get_object_or_404(
        OrderItem.objects.select_for_update().select_related("order", "product_info"),
        pk=item_id,
        product_info__shop=shop,
    )
    if item.order.state == "basket" or item.state == "basket":
        raise ValidationError({"state": "Позиция корзины еще не подтверждена."})
    if item.state == "canceled":
        raise ValidationError({"state": "Отмененную позицию нельзя изменить."})

    if new_state == "canceled":
        if item.state in {"sent", "delivered"}:
            raise ValidationError(
                {"state": "Магазин не может отменить позицию после отправки."}
            )
        old_state = item.state
        release_item_reserve(item)
        item.state = "canceled"
        item.save(update_fields=["state"])
        logger.info(
            "[update_shop_order_item_state] shop_order_item_canceled user_id=%s shop_id=%s item_id=%s old_state=%s",
            user.pk,
            shop.pk,
            item.pk,
            old_state,
        )
        recalculate_order_state(item.order)
        return item

    try:
        current_index = SHOP_STATE_ORDER.index(item.state)
        new_index = SHOP_STATE_ORDER.index(new_state)
    except ValueError as exc:
        raise ValidationError(
            {"state": "Недопустимый переход статуса позиции."}
        ) from exc

    if new_index != current_index + 1:
        raise ValidationError(
            {"state": "Магазин может переводить позицию только на следующий статус."}
        )

    old_state = item.state
    if new_state == "sent":
        ship_item_stock(item)
    item.state = new_state
    item.save(update_fields=["state"])
    logger.info(
        "[update_shop_order_item_state] shop_order_item_state_updated user_id=%s shop_id=%s item_id=%s old_state=%s new_state=%s",
        user.pk,
        shop.pk,
        item.pk,
        old_state,
        new_state,
    )
    recalculate_order_state(item.order)
    return item


# 4. Административные операции ----
def get_all_orders() -> QuerySet[Order]:
    return Order.objects.exclude(state="basket").order_by("id")


def get_admin_order(pk: int) -> Order:
    return get_object_or_404(Order, pk=pk)


@transaction.atomic
def update_order_state_by_admin(
    admin_user: User,
    order: Order,
    *,
    new_state: str | None,
    cancellation_reason: str = "",
) -> Order:
    if new_state == "canceled":
        if OrderItem.objects.filter(
            order=order, state__in=["sent", "delivered"]
        ).exists():
            raise ValidationError(
                {
                    "state": "Нельзя отменить заказ с отправленными или доставленными позициями."
                }
            )
        cancel_order_items(order)
        order.state = "canceled"
        order.cancellation_reason = cancellation_reason
        order.save(update_fields=["state", "cancellation_reason", "updated_at"])
        logger.info(
            "[update_order_state_by_admin] order_canceled_by_admin admin_user_id=%s order_id=%s",
            admin_user.pk,
            order.pk,
        )
        return order

    if new_state:
        old_state = order.state
        order.state = new_state
        if cancellation_reason:
            order.cancellation_reason = cancellation_reason
            order.save(update_fields=["state", "cancellation_reason", "updated_at"])
        else:
            order.save(update_fields=["state", "updated_at"])
        logger.info(
            "[update_order_state_by_admin] order_state_updated_by_admin admin_user_id=%s order_id=%s old_state=%s new_state=%s",
            admin_user.pk,
            order.pk,
            old_state,
            order.state,
        )
    return order


@transaction.atomic
def update_order_item_state_by_admin(
    admin_user: User, *, item_id: int, new_state: str
) -> OrderItem:
    item = get_object_or_404(
        OrderItem.objects.select_for_update().select_related("order", "product_info"),
        pk=item_id,
    )
    old_state = item.state

    if item.state in {"sent", "delivered"} and new_state not in {
        "sent",
        "delivered",
        "canceled",
    }:
        raise ValidationError(
            {
                "state": (
                    "Нельзя вернуть отправленную или доставленную позицию "
                    "к статусу до отправки: складской остаток уже списан."
                )
            }
        )
    if item.state == "delivered" and new_state == "sent":
        raise ValidationError(
            {"state": "Нельзя вернуть доставленную позицию в статус sent."}
        )
    if item.state in {"sent", "delivered"} and new_state == "canceled":
        raise ValidationError(
            {"state": "Нельзя отменить отправленную или доставленную позицию."}
        )
    if new_state == "canceled" and item.state not in {"sent", "delivered", "canceled"}:
        release_item_reserve(item)
    if new_state in {"sent", "delivered"} and item.state not in {"sent", "delivered"}:
        ship_item_stock(item)
    item.state = new_state
    item.save(update_fields=["state"])
    logger.info(
        "[update_order_item_state_by_admin] order_item_state_updated_by_admin admin_user_id=%s item_id=%s old_state=%s new_state=%s",
        admin_user.pk,
        item.pk,
        old_state,
        new_state,
    )
    recalculate_order_state(item.order)
    return item
