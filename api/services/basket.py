import logging

from django.db import transaction
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
            "[get_current_basket] basket_created user_id=%s order_id=%s",
            user.pk,
            order.pk,
        )
    else:
        logger.debug(
            "[get_current_basket] basket_selected user_id=%s order_id=%s create=%s",
            user.pk,
            order.pk if order else None,
            create,
        )
    return order


def get_basket_items(user: User) -> QuerySet[OrderItem]:
    order = get_current_basket(user)
    if order is None:
        logger.debug(
            "[get_basket_items] basket_list_empty user_id=%s reason=no_open_basket",
            user.pk,
        )
        return OrderItem.objects.none()

    items = (
        OrderItem.objects.filter(order=order)
        .select_related("product_info__shop", "product_info__product__category")
        .order_by("id")
    )
    logger.debug(
        "[get_basket_items] basket_list_loaded user_id=%s order_id=%s item_count=%s",
        user.pk,
        order.pk,
        items.count(),
    )
    return items


def get_basket_summary(user: User) -> dict:
    order = get_current_basket(user)
    if order is None:
        return {"id": None, "state": "basket", "items": [], "total": 0}

    items = [build_basket_item_payload(item) for item in get_basket_items(user)]
    total = sum(item["line_total"] for item in items)
    logger.debug(
        "[get_basket_summary] basket_loaded user_id=%s order_id=%s item_count=%s total=%s",
        user.pk,
        order.pk,
        len(items),
        total,
    )
    return {
        "id": order.pk,
        "state": order.state,
        "items": items,
        "total": total,
    }


def build_basket_item_payload(item: OrderItem) -> dict:
    product_info = item.product_info
    available_quantity = max(
        product_info.quantity - product_info.reserved_quantity,
        0,
    )
    warnings = []
    if product_info.status != "active":
        warnings.append("Предложение больше недоступно.")
    if (
        product_info.shop.status != "active"
        or not product_info.shop.is_accepting_orders
    ):
        warnings.append("Магазин не принимает новые заказы.")
    if product_info.product.status != "active":
        warnings.append("Товар архивирован.")
    if product_info.product.category.status != "active":
        warnings.append("Категория архивирована.")
    if item.quantity > available_quantity:
        warnings.append("Количество превышает доступный остаток.")

    return {
        "id": item.pk,
        "offer_id": product_info.pk,
        "product_name": product_info.product.name,
        "offer_name": product_info.name,
        "shop_name": product_info.shop.name,
        "unit_price": product_info.price,
        "quantity": item.quantity,
        "line_total": item.quantity * product_info.price,
        "available_quantity": available_quantity,
        "state": item.state,
        "warnings": warnings,
        "is_available": not warnings,
    }


@transaction.atomic
def add_basket_item(user: User, *, product_info_id: int, quantity: int) -> OrderItem:
    logger.debug(
        "[add_basket_item] basket_add_started user_id=%s product_info_id=%s quantity=%s",
        user.pk,
        product_info_id,
        quantity,
    )

    product_info = get_object_or_404(
        ProductInfo.objects.select_related("shop", "product__category"),
        id=product_info_id,
        status="active",
        shop__status="active",
        shop__is_accepting_orders=True,
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
                "[add_basket_item] basket_add_rejected_stock user_id=%s product_info_id=%s "
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
        order_item.save(update_fields=["quantity"])

    logger.info(
        (
            "[add_basket_item] basket_item_%s user_id=%s order_id=%s item_id=%s "
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


@transaction.atomic
def update_basket_item_quantity(
    user: User, *, item_id: int, quantity: int
) -> OrderItem:
    order_item = get_object_or_404(
        OrderItem.objects.select_for_update().select_related(
            "order",
            "product_info__shop",
            "product_info__product__category",
        ),
        id=item_id,
        order__user=user,
        order__state="basket",
        state="basket",
    )
    product_info = order_item.product_info
    available_quantity = max(product_info.quantity - product_info.reserved_quantity, 0)
    if quantity > available_quantity:
        logger.warning(
            (
                "[update_basket_item_quantity] basket_update_rejected_stock "
                "user_id=%s item_id=%s product_info_id=%s requested_quantity=%s "
                "available_quantity=%s"
            ),
            user.pk,
            order_item.pk,
            product_info.pk,
            quantity,
            available_quantity,
        )
        raise ValidationError(
            {
                "quantity": f"Запрошенное количество превышает доступный остаток: {available_quantity}."
            }
        )

    order_item.quantity = quantity
    order_item.save(update_fields=["quantity"])
    logger.info(
        "[update_basket_item_quantity] basket_item_quantity_updated user_id=%s order_id=%s item_id=%s quantity=%s",
        user.pk,
        order_item.order.pk,
        order_item.pk,
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
        (
            "[delete_basket_item] basket_item_deleted user_id=%s order_id=%s "
            "item_id=%s product_info_id=%s"
        ),
        user.pk,
        deleted_order_id,
        deleted_item_id,
        deleted_product_info_id,
    )


def clear_basket(user: User) -> None:
    order = get_current_basket(user)
    if order is None:
        logger.debug(
            "[clear_basket] basket_clear_skipped user_id=%s reason=no_open_basket",
            user.pk,
        )
        return

    deleted_count, _ = OrderItem.objects.filter(order=order).delete()
    logger.info(
        "[clear_basket] basket_cleared user_id=%s order_id=%s deleted_count=%s",
        user.pk,
        order.pk,
        deleted_count,
    )
