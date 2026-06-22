import logging
from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from api.models import Contact, User

logger = logging.getLogger(__name__)


# 1. Контакты ----
def get_user_contacts(user: User) -> QuerySet[Contact]:
    contacts = Contact.objects.filter(user=user).order_by("id")
    logger.debug(
        "contact_list_loaded user_id=%s contact_count=%s",
        user.pk,
        contacts.count(),
    )
    return contacts


def create_contact(user: User, contact_data: dict[str, Any]) -> Contact:
    contact = Contact(user=user, **contact_data)
    contact.save()
    logger.info(
        "contact_created user_id=%s contact_id=%s",
        user.pk,
        contact.pk,
    )
    return contact


def delete_contact(user: User, contact_id: int | str | None) -> None:
    contact = get_object_or_404(Contact, id=contact_id, user=user)
    deleted_contact_id = contact.pk
    contact.delete()
    logger.info(
        "contact_deleted user_id=%s contact_id=%s",
        user.pk,
        deleted_contact_id,
    )
