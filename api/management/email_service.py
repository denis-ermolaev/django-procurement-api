import logging

from django.conf import settings
from django.core.mail import send_mail

from api.models import Order

logger = logging.getLogger(__name__)


# 1. Уведомления о заказах ----
def send_order_confirmation(order: Order) -> None:
    """Отправить письма клиенту и администраторам после подтверждения заказа."""

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
            "order_customer_email_sending order_id=%s user_id=%s",
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
            "order_customer_email_sent order_id=%s user_id=%s",
            order.pk,
            order.user.pk,
        )
    else:
        logger.warning(
            "order_customer_email_skipped order_id=%s user_id=%s reason=no_email",
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
            "order_admin_email_sending order_id=%s recipient_count=%s",
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
            "order_admin_email_sent order_id=%s recipient_count=%s",
            order.pk,
            len(admin_emails),
        )
    else:
        logger.warning(
            "order_admin_email_skipped order_id=%s reason=no_admin_emails",
            order.pk,
        )
