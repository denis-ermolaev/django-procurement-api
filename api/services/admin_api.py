import logging
from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from api.models import Category, Parameter, Product, ProductInfo, Shop, User

logger = logging.getLogger(__name__)


# 1. Пользователи ----
def get_all_users() -> QuerySet[User]:
    return User.objects.order_by("id")


def get_user(user_id: int) -> User:
    return get_object_or_404(User, pk=user_id)


def update_user(user_id: int, user_data: dict[str, Any]) -> User:
    user = get_user(user_id)
    target_type = user_data.get("type", user.type)
    target_is_staff = user_data.get("is_staff", user.is_staff)

    if target_type == "admin" and not target_is_staff:
        raise ValidationError(
            {"is_staff": "Пользователь с ролью admin должен иметь is_staff=True."}
        )
    if target_type == "shop" and not Shop.objects.filter(owner=user).exists():
        raise ValidationError(
            {
                "type": "Роль shop можно назначить только пользователю со связанным магазином."
            }
        )
    if (
        user.type == "shop"
        and target_type != "shop"
        and Shop.objects.filter(owner=user).exists()
    ):
        raise ValidationError(
            {"type": "Нельзя изменить роль пользователя, который владеет магазином."}
        )

    changed_fields: list[str] = []
    for field in ("is_active", "type", "is_staff"):
        if field in user_data:
            setattr(user, field, user_data[field])
            changed_fields.append(field)
    if changed_fields:
        user.save(update_fields=changed_fields)
    logger.info(
        "admin_user_updated user_id=%s changed_fields=%s",
        user.pk,
        changed_fields,
    )
    return user


# 2. Магазины и предложения ----
def update_shop(shop_id: int, shop_data: dict[str, Any]) -> Shop:
    shop = get_object_or_404(Shop, pk=shop_id)
    changed_fields: list[str] = []
    for field in ("name", "url", "status"):
        if field in shop_data:
            setattr(shop, field, shop_data[field])
            changed_fields.append(field)
    if changed_fields:
        changed_fields.append("updated_at")
        shop.save(update_fields=changed_fields)
    logger.info(
        "admin_shop_updated shop_id=%s changed_fields=%s",
        shop.pk,
        changed_fields,
    )
    return shop


def update_offer(product_info_id: int, offer_data: dict[str, Any]) -> ProductInfo:
    offer = get_object_or_404(ProductInfo, pk=product_info_id)
    if "quantity" in offer_data and offer_data["quantity"] < offer.reserved_quantity:
        raise ValidationError(
            {
                "quantity": (
                    "Остаток не может быть меньше уже зарезервированного количества."
                )
            }
        )

    changed_fields: list[str] = []
    for field in ("name", "quantity", "price", "price_rrc", "status"):
        if field in offer_data:
            setattr(offer, field, offer_data[field])
            changed_fields.append(field)
    if changed_fields:
        offer.save(update_fields=changed_fields)
    logger.info(
        "admin_offer_updated product_info_id=%s changed_fields=%s",
        offer.pk,
        changed_fields,
    )
    return offer


# 3. Каталог ----
def get_all_categories() -> QuerySet[Category]:
    return Category.objects.order_by("id")


def create_category(category_data: dict[str, Any]) -> Category:
    category = Category.objects.create(**category_data)
    logger.info("admin_category_created category_id=%s", category.pk)
    return category


def update_category(category_id: int, category_data: dict[str, Any]) -> Category:
    category = get_object_or_404(Category, pk=category_id)
    changed_fields: list[str] = []
    for field in ("name", "status"):
        if field in category_data:
            setattr(category, field, category_data[field])
            changed_fields.append(field)
    if changed_fields:
        category.save(update_fields=changed_fields)
    logger.info(
        "admin_category_updated category_id=%s changed_fields=%s",
        category.pk,
        changed_fields,
    )
    return category


def get_all_products() -> QuerySet[Product]:
    return Product.objects.select_related("category").order_by("id")


def create_product(product_data: dict[str, Any]) -> Product:
    product = Product.objects.create(**product_data)
    logger.info("admin_product_created product_id=%s", product.pk)
    return product


def update_product(product_id: int, product_data: dict[str, Any]) -> Product:
    product = get_object_or_404(Product, pk=product_id)
    changed_fields: list[str] = []
    for field in ("name", "category", "status"):
        if field in product_data:
            setattr(product, field, product_data[field])
            changed_fields.append(field)
    if changed_fields:
        product.save(update_fields=changed_fields)
    logger.info(
        "admin_product_updated product_id=%s changed_fields=%s",
        product.pk,
        changed_fields,
    )
    return product


def get_all_parameters() -> QuerySet[Parameter]:
    return Parameter.objects.order_by("id")


def create_parameter(parameter_data: dict[str, Any]) -> Parameter:
    parameter = Parameter.objects.create(**parameter_data)
    logger.info("admin_parameter_created parameter_id=%s", parameter.pk)
    return parameter


def update_parameter(parameter_id: int, parameter_data: dict[str, Any]) -> Parameter:
    parameter = get_object_or_404(Parameter, pk=parameter_id)
    if "name" in parameter_data:
        parameter.name = parameter_data["name"]
        parameter.save(update_fields=["name"])
    logger.info("admin_parameter_updated parameter_id=%s", parameter.pk)
    return parameter
