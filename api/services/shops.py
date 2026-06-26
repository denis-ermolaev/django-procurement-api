import logging
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from api.models import Product, ProductInfo, Shop, User

logger = logging.getLogger(__name__)


# 1. Регистрация и модерация магазинов ----
@transaction.atomic
def register_shop(shop_data: dict[str, Any]) -> tuple[User, Shop]:
    user = User.objects.create_user(
        email=shop_data["email"],
        password=shop_data["password"],
        first_name=shop_data.get("first_name", ""),
        last_name=shop_data.get("last_name", ""),
        type="shop",
    )
    shop = Shop.objects.create(
        owner=user,
        name=shop_data["shop_name"],
        url=shop_data.get("url", ""),
        status="pending",
    )
    logger.info(
        "[register_shop] shop_registered user_id=%s shop_id=%s status=%s",
        user.pk,
        shop.pk,
        shop.status,
    )
    return user, shop


def approve_shop(admin_user: User, *, shop_id: int) -> Shop:
    shop = get_object_or_404(Shop, pk=shop_id)
    old_status = shop.status
    shop.status = "active"
    shop.save(update_fields=["status", "updated_at"])
    logger.info(
        "[approve_shop] shop_approved admin_user_id=%s shop_id=%s old_status=%s new_status=%s",
        admin_user.pk,
        shop.pk,
        old_status,
        shop.status,
    )
    return shop


def block_shop(admin_user: User, *, shop_id: int) -> Shop:
    shop = get_object_or_404(Shop, pk=shop_id)
    old_status = shop.status
    shop.status = "blocked"
    shop.save(update_fields=["status", "updated_at"])
    logger.info(
        "[block_shop] shop_blocked admin_user_id=%s shop_id=%s old_status=%s new_status=%s",
        admin_user.pk,
        shop.pk,
        old_status,
        shop.status,
    )
    return shop


# 2. Профиль и предложения магазина ----
def get_user_shop(user: User) -> Shop:
    return get_object_or_404(Shop, owner=user)


def update_user_shop(user: User, shop_data: dict[str, Any]) -> Shop:
    shop = get_user_shop(user)
    changed_fields: list[str] = []
    for field in ("name", "url", "is_accepting_orders"):
        if field in shop_data:
            setattr(shop, field, shop_data[field])
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        shop.save(update_fields=changed_fields)
    logger.info(
        "[update_user_shop] shop_profile_updated user_id=%s shop_id=%s changed_fields=%s",
        user.pk,
        shop.pk,
        changed_fields,
    )
    return shop


def get_shop_offers(user: User) -> QuerySet[ProductInfo]:
    shop = get_user_shop(user)
    offers = (
        ProductInfo.objects.filter(shop=shop)
        .select_related("product", "shop")
        .order_by("id")
    )
    logger.debug(
        "[get_shop_offers] shop_offers_loaded user_id=%s shop_id=%s offer_count=%s",
        user.pk,
        shop.pk,
        offers.count(),
    )
    return offers


def create_shop_offer(user: User, offer_data: dict[str, Any]) -> ProductInfo:
    shop = get_user_shop(user)
    if shop.status != "active":
        raise ValidationError({"shop": "Магазин должен быть активным для продажи."})

    product = get_object_or_404(Product, pk=offer_data["product"].pk, status="active")
    if product.category.status != "active":
        raise ValidationError(
            {"product": "Нельзя создать предложение для архивной категории."}
        )

    offer = ProductInfo.objects.create(
        shop=shop,
        product=product,
        external_id=offer_data.get("external_id", ""),
        model=offer_data.get("model", ""),
        name=offer_data["name"],
        quantity=offer_data["quantity"],
        price=offer_data["price"],
        price_rrc=offer_data["price_rrc"],
        status=offer_data.get("status", "active"),
    )
    logger.info(
        "[create_shop_offer] shop_offer_created user_id=%s shop_id=%s product_info_id=%s product_id=%s",
        user.pk,
        shop.pk,
        offer.pk,
        product.pk,
    )
    return offer


def update_shop_offer(
    user: User, *, product_info_id: int, offer_data: dict[str, Any]
) -> ProductInfo:
    shop = get_user_shop(user)
    if shop.status != "active":
        raise ValidationError({"shop": "Магазин должен быть активным для продажи."})

    offer = get_object_or_404(ProductInfo, pk=product_info_id, shop=shop)
    if "quantity" in offer_data and offer_data["quantity"] < offer.reserved_quantity:
        raise ValidationError(
            {
                "quantity": (
                    "Остаток не может быть меньше уже зарезервированного количества."
                )
            }
        )

    changed_fields: list[str] = []
    for field in (
        "external_id",
        "model",
        "name",
        "quantity",
        "price",
        "price_rrc",
        "status",
    ):
        if field in offer_data:
            setattr(offer, field, offer_data[field])
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        offer.save(update_fields=changed_fields)
    logger.info(
        "[update_shop_offer] shop_offer_updated user_id=%s shop_id=%s product_info_id=%s changed_fields=%s",
        user.pk,
        shop.pk,
        offer.pk,
        changed_fields,
    )
    return offer


# 3. Административные списки ----
def get_all_shops(search: str | None = None) -> QuerySet[Shop]:
    qs = Shop.objects.select_related("owner").order_by("id")
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(owner__email__icontains=search))
    return qs


def get_all_offers(search: str | None = None) -> QuerySet[ProductInfo]:
    qs = ProductInfo.objects.select_related("shop", "product").order_by("id")
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(product__name__icontains=search))
    return qs
