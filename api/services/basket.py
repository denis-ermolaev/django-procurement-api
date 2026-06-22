import logging

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from api.models import Order, OrderItem, ProductInfo, User

logger = logging.getLogger(__name__)


# 1. Корзина ----
def get_current_basket(user: User, *, create: bool = False) -> Order | None:
    # 1.1. Текущей считаем самую раннюю открытую корзину пользователя.
    # Это сохраняет предсказуемое поведение даже если в БД остались старые
    # дублирующие basket-заказы.
    order = Order.objects.filter(user=user, state="basket").order_by("id").first()

    if order is None and create:
        order = Order.objects.create(user=user, state="basket")
        logger.info(
            "basket_created user_id=%s order_id=%s",
            user.pk,
            order.pk,
        )
    else:
        logger.debug(
            "basket_selected user_id=%s order_id=%s create=%s",
            user.pk,
            order.pk if order else None,
            create,
        )
    return order


def get_basket_items(user: User) -> QuerySet[OrderItem]:
    order = get_current_basket(user)
    if order is None:
        logger.debug("basket_list_empty user_id=%s reason=no_open_basket", user.pk)
        return OrderItem.objects.none()

    items = OrderItem.objects.filter(order=order).order_by("id")
    logger.debug(
        "basket_list_loaded user_id=%s order_id=%s item_count=%s",
        user.pk,
        order.pk,
        items.count(),
    )
    return items


def add_basket_item(user: User, *, product_info_id: int, quantity: int) -> OrderItem:
    logger.debug(
        "basket_add_started user_id=%s product_info_id=%s quantity=%s",
        user.pk,
        product_info_id,
        quantity,
    )

    product_info = get_object_or_404(
        ProductInfo,
        id=product_info_id,
        status="active",
        shop__status="active",
        product__status="active",
        product__category__status="active",
    )
    order = get_current_basket(user)
    current_quantity = 0
    if order:
        current_quantity = (
            OrderItem.objects.filter(order=order, product_info=product_info)
            .values_list("quantity", flat=True)
            .first()
            or 0
        )

    available_quantity = max(product_info.quantity - product_info.reserved_quantity, 0)
    if current_quantity + quantity > available_quantity:
        logger.warning(
            (
                "basket_add_rejected_stock user_id=%s product_info_id=%s "
                "requested_quantity=%s current_quantity=%s available_quantity=%s"
            ),
            user.pk,
            product_info.pk,
            quantity,
            current_quantity,
            available_quantity,
        )
        raise ValidationError(
            {
                "quantity": (
                    "Запрошенное количество превышает доступный остаток. "
                    f"Доступно: {available_quantity}, уже в корзине: "
                    f"{current_quantity}."
                )
            }
        )

    if order is None:
        order = get_current_basket(user, create=True)
        assert order is not None

    order_item, created = OrderItem.objects.get_or_create(
        order=order,
        product_info=product_info,
        defaults={"quantity": quantity, "state": "basket"},
    )

    if not created:
        order_item.quantity += quantity
        order_item.save()

    logger.info(
        (
            "basket_item_%s user_id=%s order_id=%s item_id=%s "
            "product_info_id=%s quantity=%s"
        ),
        "created" if created else "updated",
        user.pk,
        order.pk,
        order_item.pk,
        product_info.pk,
        order_item.quantity,
    )
    return order_item


def delete_basket_item(
    user: User, *, item_id: int, order_id: int | None = None
) -> None:
    item_filters = {
        "id": item_id,
        "order__user": user,
        "order__state": "basket",
    }
    if order_id:
        item_filters["order_id"] = order_id

    order_item = get_object_or_404(OrderItem, **item_filters)
    deleted_item_id = order_item.pk
    deleted_order_id = order_item.order.pk
    deleted_product_info_id = order_item.product_info.pk
    order_item.delete()

    logger.info(
        ("basket_item_deleted user_id=%s order_id=%s item_id=%s product_info_id=%s"),
        user.pk,
        deleted_order_id,
        deleted_item_id,
        deleted_product_info_id,
    )
