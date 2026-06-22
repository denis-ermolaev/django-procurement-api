import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from django.core.management.base import CommandError

from api.models import Category, Parameter, Product, ProductInfo, ProductParameter, Shop

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
    parameter_count: int = 0
    skipped_messages: list[str] = field(default_factory=list)


# 2. Загрузка YAML-прайса ----
def load_shop_data(file_path: str) -> ShopDataLoadResult:
    data = read_shop_yaml(file_path)
    logger.info("shop_data_load_started file_path=%s", file_path)

    shop_name = data.get("shop")
    if not shop_name:
        logger.error(
            "shop_data_load_failed file_path=%s reason=missing_shop", file_path
        )
        raise CommandError("YAML file must contain the 'shop' field.")

    shop = load_shop(data)
    cat_by_id = load_categories(data.get("categories", []), shop)
    result = load_goods(data.get("goods", []), shop, cat_by_id)

    logger.info(
        (
            "shop_data_load_completed shop_id=%s loaded_count=%s "
            "skipped_count=%s created_products=%s updated_products=%s "
            "created_offers=%s updated_offers=%s parameter_count=%s"
        ),
        shop.pk,
        result.loaded_count,
        result.skipped_count,
        result.created_products,
        result.updated_products,
        result.created_offers,
        result.updated_offers,
        result.parameter_count,
    )
    return result


def read_shop_yaml(file_path: str) -> dict[str, Any]:
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_shop(data: dict[str, Any]) -> Shop:
    shop_name = data["shop"]
    shop_url = data.get("url", "")
    shop, created = Shop.objects.get_or_create(
        name=shop_name,
        defaults={"url": shop_url},
    )
    logger.info(
        "shop_data_shop_%s shop_id=%s shop_name=%s",
        "created" if created else "selected",
        shop.pk,
        shop.name,
    )
    if not created and shop_url and shop.url != shop_url:
        shop.url = shop_url
        shop.save(update_fields=["url"])
        logger.info("shop_data_shop_url_updated shop_id=%s", shop.pk)
    return shop


def load_categories(
    categories: list[dict[str, Any]], shop: Shop
) -> dict[int, Category]:
    cat_by_id = {}
    for cat_data in categories:
        cat_id = cat_data["id"]
        category, created = Category.objects.get_or_create(name=cat_data["name"])
        category.shops.add(shop)
        cat_by_id[cat_id] = category
        logger.debug(
            "shop_data_category_%s source_category_id=%s category_id=%s shop_id=%s",
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

        product, product_created = Product.objects.update_or_create(
            name=good["name"], defaults={"category": category}
        )
        if product_created:
            result.created_products += 1
        else:
            result.updated_products += 1

        product_info, offer_created = ProductInfo.objects.update_or_create(
            product=product,
            shop=shop,
            name=good["name"],
            defaults={
                "quantity": good["quantity"],
                "price": good["price"],
                "price_rrc": good["price_rrc"],
            },
        )
        if offer_created:
            result.created_offers += 1
        else:
            result.updated_offers += 1

        logger.debug(
            (
                "shop_data_offer_%s shop_id=%s product_id=%s product_info_id=%s "
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
