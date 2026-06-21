from django.conf import settings
from django.core.mail import send_mail

from api.models import Order


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
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [customer_email],
            fail_silently=False,
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
        send_mail(
            f"Новый подтверждённый заказ #{order.pk}",
            admin_message,
            settings.DEFAULT_FROM_EMAIL,
            admin_emails,
            fail_silently=False,
        )
