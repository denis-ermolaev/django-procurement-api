# api/email_service.py
from django.conf import settings
from django.core.mail import send_mail

from api.models import Order


def send_order_confirmation(order: Order) -> None:
    """
    Отправляет письма клиенту и администраторам после подтверждения заказа.
    """
    # Определяем email клиента
    if order.user.email:
        customer_email = order.user.email
    else:
        # Если нет контакта и пользователь без email — пропускаем
        customer_email = None

    # Тема и текст письма
    subject = f"Заказ #{order.pk} подтверждён"
    message = (
        f"Ваш заказ #{order.pk} успешно подтверждён.\n"
        f"Дата: {order.dt}\n"
        f"Статус: {order.state}\n"
    )

    # Отправляем клиенту
    if customer_email:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [customer_email],
            fail_silently=False,
        )

    # Отправляем всем администраторам
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
