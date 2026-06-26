import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml
from django.core.management.base import CommandError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_rq import job
from rest_framework.exceptions import ValidationError

from api.models import (
    Category,
    ImportJob,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)

logger = logging.getLogger(__name__)


# 1. Результат загрузки ----
@dataclass
class ShopDataLoadResult:
    loaded_count: int = 0
    skipped_count: int = 0
    created_products: int = 0
    updated_products: int = 0
    created_offers: int = 0
    updated_offers: int = 0
    hidden_offers: int = 0
    parameter_count: int = 0
    skipped_messages: list[str] = field(default_factory=list)
    seen_external_ids: set[str] = field(default_factory=set)


# 2. Загрузка YAML-прайса ----
def load_shop_data(file_path: str) -> ShopDataLoadResult:
    data = read_shop_yaml(file_path)
    logger.info("[load_shop_data] shop_data_load_started file_path=%s", file_path)

    shop_name = data.get("shop")
    if not shop_name:
        logger.error(
            "[load_shop_data] shop_data_load_failed file_path=%s reason=missing_shop",
            file_path,
        )
        raise CommandError("YAML file must contain the 'shop' field.")

    shop = load_shop(data)
    cat_by_id = load_categories(data.get("categories", []), shop)
    result = load_goods(data.get("goods", []), shop, cat_by_id)

    logger.info(
        (
            "[load_shop_data] shop_data_load_completed shop_id=%s loaded_count=%s "
            "skipped_count=%s created_products=%s updated_products=%s "
            "created_offers=%s updated_offers=%s hidden_offers=%s parameter_count=%s"
        ),
        shop.pk,
        result.loaded_count,
        result.skipped_count,
        result.created_products,
        result.updated_products,
        result.created_offers,
        result.updated_offers,
        result.hidden_offers,
        result.parameter_count,
    )
    return result


def read_shop_yaml(file_path: str) -> dict[str, Any]:
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_shop_yaml_content(content: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise ValidationError({"file": "YAML не читается."}) from exc
    if not isinstance(data, dict):
        raise ValidationError({"file": "YAML должен содержать объект верхнего уровня."})
    return data


def load_shop(data: dict[str, Any]) -> Shop:
    shop_name = data["shop"]
    shop_url = data.get("url", "")
    shop_status = data.get("status", "active")
    owner_email = data.get("owner_email")

    shop, created = Shop.objects.get_or_create(
        name=shop_name,
        defaults={"url": shop_url, "status": shop_status},
    )
    logger.info(
        "[load_shop] shop_data_shop_%s shop_id=%s shop_name=%s",
        "created" if created else "selected",
        shop.pk,
        shop.name,
    )

    # Привязка владельца магазина, если указан owner_email в YAML
    if owner_email and shop.owner is None:
        owner, created = User.objects.get_or_create(
            email=owner_email,
            defaults={
                "first_name": shop_name,
                "type": "shop",
                "is_active": True,
            },
        )
        if created:
            if not owner.has_usable_password():
                owner.set_unusable_password()
                owner.save(update_fields=["password"])
        elif owner.type != "shop":
            logger.warning(
                "[load_shop] owner_type_mismatch email=%s existing_type=%s expected_type=shop",
                owner_email,
                owner.type,
            )
            raise CommandError(
                f"Пользователь {owner_email} уже существует с типом «{owner.type}», "
                f"а не «shop». Невозможно назначить владельцем магазина."
            )
        shop.owner = owner
        shop.save(update_fields=["owner", "updated_at"])
        logger.info(
            "[load_shop] shop_data_owner_set shop_id=%s owner_email=%s",
            shop.pk,
            owner_email,
        )

    changed_fields: list[str] = []
    if not created and shop_url and shop.url != shop_url:
        shop.url = shop_url
        changed_fields.append("url")
    if not created and shop.owner is None and shop.status != shop_status:
        shop.status = shop_status
        changed_fields.append("status")
    if changed_fields:
        changed_fields.append("updated_at")
        shop.save(update_fields=changed_fields)
        logger.info(
            "[load_shop] shop_data_shop_updated shop_id=%s changed_fields=%s",
            shop.pk,
            changed_fields,
        )
    return shop


def load_categories(
    categories: list[dict[str, Any]], shop: Shop
) -> dict[int, Category]:
    cat_by_id = {}
    for cat_data in categories:
        cat_id = cat_data["id"]
        category_status = cat_data.get("status", "active")
        category, created = Category.objects.get_or_create(
            name=cat_data["name"], defaults={"status": category_status}
        )
        if not created and category.status != category_status:
            category.status = category_status
            category.save(update_fields=["status"])
        category.shops.add(shop)
        cat_by_id[cat_id] = category
        logger.debug(
            "[load_categories] shop_data_category_%s source_category_id=%s category_id=%s shop_id=%s",
            "created" if created else "selected",
            cat_id,
            category.pk,
            shop.pk,
        )
    return cat_by_id


def load_goods(
    goods: list[dict[str, Any]],
    shop: Shop,
    cat_by_id: dict[int, Category],
) -> ShopDataLoadResult:
    result = ShopDataLoadResult()

    for good in goods:
        category = cat_by_id.get(good["category"])
        if not category:
            result.skipped_count += 1
            message = (
                f"Category id {good['category']} not found, skipping {good['name']}"
            )
            result.skipped_messages.append(message)
            logger.warning(
                (
                    "shop_data_good_skipped_missing_category shop_id=%s "
                    "source_category_id=%s good_name=%s"
                ),
                shop.pk,
                good["category"],
                good["name"],
            )
            continue

        product, product_created = get_or_update_import_product(good, category, shop)
        if product_created:
            result.created_products += 1
        else:
            result.updated_products += 1

        product_info, offer_created = update_import_offer(
            good,
            shop=shop,
            product=product,
        )
        if product_info.external_id:
            result.seen_external_ids.add(product_info.external_id)
        if offer_created:
            result.created_offers += 1
        else:
            result.updated_offers += 1

        logger.debug(
            (
                "[load_goods] shop_data_offer_%s shop_id=%s product_id=%s product_info_id=%s "
                "quantity=%s price=%s"
            ),
            "created" if offer_created else "updated",
            shop.pk,
            product.pk,
            product_info.pk,
            product_info.quantity,
            product_info.price,
        )

        result.parameter_count += replace_product_parameters(product_info, good)
        result.loaded_count += 1

    return result


def get_or_update_import_product(
    good: dict[str, Any],
    category: Category,
    shop: Shop,
) -> tuple[Product, bool]:
    external_id = str(good.get("id", "")).strip()
    existing_offer = None
    if external_id:
        existing_offer = (
            ProductInfo.objects.filter(
                shop=shop,
                external_id=external_id,
            )
            .select_related("product")
            .first()
        )

    if existing_offer:
        product = existing_offer.product
        changed_fields = []
        if product.name != good["name"]:
            product.name = good["name"]
            changed_fields.append("name")
        if product.category_id != category.pk:
            product.category = category
            changed_fields.append("category")
        product_status = good.get("product_status", "active")
        if product.status != product_status:
            product.status = product_status
            changed_fields.append("status")
        if changed_fields:
            product.save(update_fields=changed_fields)
        return product, False

    return Product.objects.update_or_create(
        name=good["name"],
        defaults={
            "category": category,
            "status": good.get("product_status", "active"),
        },
    )


def update_import_offer(
    good: dict[str, Any],
    *,
    shop: Shop,
    product: Product,
) -> tuple[ProductInfo, bool]:
    external_id = str(good.get("id", "")).strip()
    model_name = str(good.get("model", "")).strip()
    defaults = {
        "product": product,
        "name": good["name"],
        "model": model_name,
        "quantity": good["quantity"],
        "price": good["price"],
        "price_rrc": good["price_rrc"],
        "status": good.get("status", "active"),
    }

    if external_id:
        offer = ProductInfo.objects.filter(shop=shop, external_id=external_id).first()
        if offer is None:
            offer = ProductInfo.objects.filter(
                shop=shop,
                product=product,
                name=good["name"],
                external_id="",
            ).first()
        if offer is None:
            return ProductInfo.objects.create(
                shop=shop,
                external_id=external_id,
                **defaults,
            ), True

        for field_name, value in defaults.items():
            setattr(offer, field_name, value)
        offer.external_id = external_id
        offer.save(update_fields=[*defaults.keys(), "external_id", "updated_at"])
        return offer, False

    return ProductInfo.objects.update_or_create(
        product=product,
        shop=shop,
        name=good["name"],
        defaults=defaults,
    )


def replace_product_parameters(product_info: ProductInfo, good: dict[str, Any]) -> int:
    ProductParameter.objects.filter(product_info=product_info).delete()
    parameter_count = 0
    for param_name, param_value in good.get("parameters", {}).items():
        parameter, _ = Parameter.objects.get_or_create(name=param_name)
        ProductParameter.objects.create(
            product_info=product_info,
            parameter=parameter,
            value=str(param_value),
        )
        parameter_count += 1
    return parameter_count


# 3. API-импорт поставщика (RQ-задача) ----
@job("default")
def import_shop_data_async(user_id: int, *, import_job_id: int, content: str) -> None:
    """Фоновый импорт прайса через RQ-воркер.

    ``import_shop_data`` обёрнута в ``@transaction.atomic``; при ошибке
    откатывается и ``import_job.status = "failed"``.  Поэтому сохраняем
    статус ошибки здесь — после отката основной транзакции.
    """
    user = get_object_or_404(User, pk=user_id)
    import_job = ImportJob.objects.select_related("shop").get(pk=import_job_id)
    try:
        import_shop_data(user, content=content, import_job=import_job)
        logger.info(
            "[import_shop_data_async] rq_import_completed import_job_id=%s shop_id=%s",
            import_job_id,
            import_job.shop.pk,
        )
    except (ValidationError, CommandError, Exception):
        # Откат @transaction.atomic откатил сохранение статуса внутри
        # import_shop_data — сохраняем здесь в новой транзакции.
        # SystemExit и KeyboardInterrupt НЕ перехватываются — они унаследованы
        # от BaseException, а не Exception.
        ImportJob.objects.filter(pk=import_job_id).update(
            status="failed",
            completed_at=timezone.now(),
            error_log=traceback.format_exc(),
        )
        logger.exception(
            "[import_shop_data_async] rq_import_failed import_job_id=%s",
            import_job_id,
        )


@transaction.atomic
def import_shop_data(
    user: User, *, content: str, import_job: ImportJob | None = None
) -> ShopDataLoadResult:
    shop = get_object_or_404(Shop, owner=user)
    if shop.status != "active":
        raise ValidationError({"shop": "Импорт доступен только активному магазину."})

    # Создаём задачу импорта, если не передана извне
    if import_job is None:
        import_job = ImportJob.objects.create(
            shop=shop,
            status="processing",
        )

    try:
        data = read_shop_yaml_content(content)
        validate_shop_import_data(data, shop)
        logger.info(
            "[import_shop_data] shop_import_started user_id=%s shop_id=%s",
            user.pk,
            shop.pk,
        )

        cat_by_id = load_categories(data.get("categories", []), shop)
        result = load_goods(data.get("goods", []), shop, cat_by_id)
        result.hidden_offers = hide_missing_import_offers(
            shop, result.seen_external_ids
        )

        # Обновляем задачу импорта — успех
        import_job.status = "completed"
        import_job.completed_at = timezone.now()
        import_job.stats = {
            "loaded_count": result.loaded_count,
            "created_offers": result.created_offers,
            "updated_offers": result.updated_offers,
            "hidden_offers": result.hidden_offers,
        }
        import_job.save(update_fields=["status", "completed_at", "stats"])

        logger.info(
            (
                "[import_shop_data] shop_import_completed user_id=%s shop_id=%s "
                "loaded_count=%s created_offers=%s updated_offers=%s hidden_offers=%s"
            ),
            user.pk,
            shop.pk,
            result.loaded_count,
            result.created_offers,
            result.updated_offers,
            result.hidden_offers,
        )
        return result
    except Exception:
        import_job.status = "failed"
        import_job.completed_at = timezone.now()
        import_job.error_log = traceback.format_exc()
        import_job.save(update_fields=["status", "completed_at", "error_log"])
        logger.exception(
            "[import_shop_data] shop_import_failed user_id=%s shop_id=%s",
            user.pk,
            shop.pk,
        )
        raise


def validate_shop_import_data(data: dict[str, Any], shop: Shop) -> None:
    errors = []
    if data.get("shop") != shop.name:
        errors.append("Поле shop должно совпадать с названием текущего магазина.")

    raw_categories = data.get("categories")
    raw_goods = data.get("goods")
    if not isinstance(raw_categories, list) or not raw_categories:
        errors.append("Поле categories должно быть непустым списком.")
    if not isinstance(raw_goods, list) or not raw_goods:
        errors.append("Поле goods должно быть непустым списком.")
    if errors:
        raise ValidationError({"import": errors})

    categories = cast(list[dict[str, Any]], raw_categories)
    goods = cast(list[dict[str, Any]], raw_goods)
    category_ids = set()
    for index, category in enumerate(categories):
        if not isinstance(category, dict):
            errors.append(f"categories[{index}] должен быть объектом.")
            continue
        if "id" not in category or "name" not in category:
            errors.append(f"categories[{index}] должен содержать id и name.")
            continue
        category_ids.add(category["id"])

    external_ids = set()
    for index, good in enumerate(goods):
        if not isinstance(good, dict):
            errors.append(f"goods[{index}] должен быть объектом.")
            continue
        for field_name in ("id", "category", "name", "price", "price_rrc", "quantity"):
            if field_name not in good:
                errors.append(f"goods[{index}] должен содержать {field_name}.")
        if good.get("category") not in category_ids:
            errors.append(f"goods[{index}] ссылается на неизвестную категорию.")
        external_id = str(good.get("id", "")).strip()
        if not external_id:
            errors.append(f"goods[{index}].id не должен быть пустым.")
        elif external_id in external_ids:
            errors.append(f"goods[{index}].id дублируется в прайсе.")
        external_ids.add(external_id)
        price = good.get("price")
        price_rrc = good.get("price_rrc")
        quantity = good.get("quantity")
        if not is_positive_number(price):
            errors.append(f"goods[{index}].price должен быть больше 0.")
        if not is_non_negative_number(price_rrc):
            errors.append(f"goods[{index}].price_rrc не может быть отрицательным.")
        if not is_non_negative_number(quantity):
            errors.append(f"goods[{index}].quantity не может быть отрицательным.")

    if errors:
        raise ValidationError({"import": errors})


def hide_missing_import_offers(shop: Shop, seen_external_ids: set[str]) -> int:
    if not seen_external_ids:
        return 0
    return (
        ProductInfo.objects.filter(shop=shop)
        .exclude(external_id="")
        .exclude(external_id__in=seen_external_ids)
        .update(status="hidden")
    )


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_positive_number(value: Any) -> bool:
    return is_number(value) and value > 0


def is_non_negative_number(value: Any) -> bool:
    return is_number(value) and value >= 0
