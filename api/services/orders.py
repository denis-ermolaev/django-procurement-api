import logging

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from api.management.email_service import send_order_confirmation
from api.models import Contact, Order, OrderItem, User

logger = logging.getLogger(__name__)


# 1. Заказы ----
def confirm_order(user: User, *, order_id: int, contact_id: int) -> Order:
    logger.debug(
        "order_confirm_started user_id=%s order_id=%s contact_id=%s",
        user.pk,
        order_id,
        contact_id,
    )

    order = get_object_or_404(Order, id=order_id, user=user, state="basket")
    if not OrderItem.objects.filter(order=order).exists():
        logger.warning(
            "order_confirm_rejected_empty_basket user_id=%s order_id=%s",
            user.pk,
            order.pk,
        )
        raise ValidationError(
            {"order_id": "Нельзя подтвердить заказ без позиций в корзине."}
        )

    contact = get_object_or_404(Contact, id=contact_id, user=user)
    order.state = "confirmed"
    order.contact = contact
    order.save()

    logger.info(
        "order_confirmed user_id=%s order_id=%s contact_id=%s",
        user.pk,
        order.pk,
        contact.pk,
    )
    send_order_confirmation(order)
    return order


def get_order_history(user: User) -> QuerySet[Order]:
    orders = Order.objects.filter(user=user).exclude(state="basket").order_by("id")
    logger.debug(
        "order_history_loaded user_id=%s order_count=%s",
        user.pk,
        orders.count(),
    )
    return orders


def get_user_order(user: User, pk: int) -> Order:
    order = get_object_or_404(Order, pk=pk, user=user)
    logger.debug(
        "order_detail_loaded user_id=%s order_id=%s state=%s",
        user.pk,
        order.pk,
        order.state,
    )
    return order


def update_order_state(order: Order, new_state: str) -> Order:
    old_state = order.state
    order.state = new_state
    order.save(update_fields=["state"])
    logger.info(
        "order_state_updated user_id=%s order_id=%s old_state=%s new_state=%s",
        order.user.pk,
        order.pk,
        old_state,
        order.state,
    )
    return order
