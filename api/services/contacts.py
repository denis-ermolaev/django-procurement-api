import logging
from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from api.models import Contact, Order, User

logger = logging.getLogger(__name__)


# 1. Контакты ----
def get_user_contacts(user: User) -> QuerySet[Contact]:
    contacts = Contact.objects.filter(user=user, is_deleted=False).order_by("id")
    logger.debug(
        "[get_user_contacts] contact_list_loaded user_id=%s contact_count=%s",
        user.pk,
        contacts.count(),
    )
    return contacts


def create_contact(user: User, contact_data: dict[str, Any]) -> Contact:
    contact = Contact(user=user, **contact_data)
    contact.save()
    logger.info(
        "[create_contact] contact_created user_id=%s contact_id=%s",
        user.pk,
        contact.pk,
    )
    return contact


def get_user_contact(user: User, contact_id: int) -> Contact:
    contact = get_object_or_404(Contact, id=contact_id, user=user, is_deleted=False)
    logger.debug(
        "[get_user_contact] contact_loaded user_id=%s contact_id=%s",
        user.pk,
        contact.pk,
    )
    return contact


def update_contact(
    user: User, contact_id: int, contact_data: dict[str, Any]
) -> Contact:
    contact = get_user_contact(user, contact_id)
    changed_fields = []
    for field in (
        "city",
        "street",
        "house",
        "structure",
        "building",
        "apartment",
        "phone",
    ):
        if field in contact_data:
            setattr(contact, field, contact_data[field])
            changed_fields.append(field)
    if changed_fields:
        contact.save(update_fields=changed_fields)
    logger.info(
        "[update_contact] contact_updated user_id=%s contact_id=%s changed_fields=%s",
        user.pk,
        contact.pk,
        changed_fields,
    )
    return contact


def delete_contact(user: User, contact_id: int) -> None:
    """Удаляет контакт пользователя по ID.

    Если по контакту есть небаскетные заказы — выполняется soft delete.
    """
    contact = get_object_or_404(Contact, id=contact_id, user=user)
    deleted_contact_id = contact.pk
    if Order.objects.filter(contact=contact).exclude(state="basket").exists():
        contact.is_deleted = True
        contact.save(update_fields=["is_deleted"])
    else:
        contact.delete()
    logger.info(
        "[delete_contact] contact_deleted user_id=%s contact_id=%s",
        user.pk,
        deleted_contact_id,
    )
