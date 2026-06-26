import logging

from django.conf import settings
from django.core.mail import send_mail
from django_rq import job

from api.models import Order, OrderItem

logger = logging.getLogger(__name__)


# 1. Уведомления о заказах ----
def send_order_confirmation(order: Order) -> None:
    """Отправить письма клиенту, магазинам и администраторам после подтверждения заказа."""

    ## 1.1. Письмо клиенту ----
    if order.user.email:
        customer_email = order.user.email
    else:
        customer_email = None

    subject = f"Заказ #{order.pk} подтверждён"
    message = (
        f"Ваш заказ #{order.pk} успешно подтверждён.\n"
        f"Дата: {order.dt}\n"
        f"Статус: {order.state}\n"
    )

    if customer_email:
        logger.info(
            "[send_order_confirmation] order_customer_email_sending order_id=%s user_id=%s",
            order.pk,
            order.user.pk,
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [customer_email],
            fail_silently=False,
        )
        logger.info(
            "[send_order_confirmation] order_customer_email_sent order_id=%s user_id=%s",
            order.pk,
            order.user.pk,
        )
    else:
        logger.warning(
            "[send_order_confirmation] order_customer_email_skipped order_id=%s user_id=%s reason=no_email",
            order.pk,
            order.user.pk,
        )

    ## 1.2. Письма администраторам ----
    admin_emails = getattr(settings, "ADMIN_EMAILS", [])
    if admin_emails:
        admin_message = (
            f"Подтверждён новый заказ #{order.pk}\n"
            f"Пользователь: {order.user}\n"
            f"Email клиента: {customer_email}\n"
            f"Статус: {order.state}\n"
        )
        logger.info(
            "[send_order_confirmation] order_admin_email_sending order_id=%s recipient_count=%s",
            order.pk,
            len(admin_emails),
        )
        send_mail(
            f"Новый подтверждённый заказ #{order.pk}",
            admin_message,
            settings.DEFAULT_FROM_EMAIL,
            admin_emails,
            fail_silently=False,
        )
        logger.info(
            "[send_order_confirmation] order_admin_email_sent order_id=%s recipient_count=%s",
            order.pk,
            len(admin_emails),
        )
    else:
        logger.warning(
            "[send_order_confirmation] order_admin_email_skipped order_id=%s reason=no_admin_emails",
            order.pk,
        )

    ## 1.3. Письма магазинам — уведомление о новых позициях в заказе ----
    notify_shops_about_new_order(order)


def notify_shops_about_new_order(order: Order) -> None:
    """Отправить уведомления магазинам о новых позициях в подтверждённом заказе."""
    items = OrderItem.objects.filter(order=order).select_related(
        "product_info__shop__owner",
        "product_info__product",
    )
    shop_items: dict[int, dict[str, str | list[str]]] = {}
    for item in items:
        shop = item.product_info.shop
        if shop.pk not in shop_items:
            shop_email = shop.owner.email if shop.owner else ""
            shop_items[shop.pk] = {
                "shop_name": shop.name,
                "shop_email": shop_email,
                "items": [],
            }
        shop_item_info = shop_items[shop.pk]["items"]
        assert isinstance(shop_item_info, list)
        shop_item_info.append(
            f"  - {item.product_info.product.name} ({item.product_info.name}) x {item.quantity}"
        )

    for shop_data in shop_items.values():
        shop_email = str(shop_data["shop_email"])
        shop_name = str(shop_data["shop_name"])
        shop_item_lines = shop_data["items"]
        assert isinstance(shop_item_lines, list)
        if not shop_email:
            logger.warning(
                "[notify_shops_about_new_order] shop_email_skipped order_id=%s shop_name=%s reason=no_owner_email",
                order.pk,
                shop_name,
            )
            continue

        shop_message_lines = [
            f"Поступил новый заказ #{order.pk} от покупателя {order.user.email}.",
            "Позиции вашего магазина в заказе:",
            *shop_item_lines,
        ]
        shop_message = "\n".join(shop_message_lines)

        logger.info(
            "[notify_shops_about_new_order] shop_email_sending order_id=%s shop_name=%s",
            order.pk,
            shop_name,
        )
        send_mail(
            f"Новый заказ #{order.pk} — позиции магазина «{shop_name}»",
            shop_message,
            settings.DEFAULT_FROM_EMAIL,
            [shop_email],
            fail_silently=False,
        )
        logger.info(
            "[notify_shops_about_new_order] shop_email_sent order_id=%s shop_name=%s",
            order.pk,
            shop_name,
        )


# 2. RQ-задачи ----
@job("default")
def send_order_confirmation_async(order_id: int) -> None:
    """Асинхронная отправка подтверждения заказа через RQ-воркер."""
    try:
        order = Order.objects.select_related("user").get(pk=order_id)
        send_order_confirmation(order)
    except Exception:
        logger.exception(
            "[send_order_confirmation_async] order_confirm_email_failed order_id=%s",
            order_id,
        )
