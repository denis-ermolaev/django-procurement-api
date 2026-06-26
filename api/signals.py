"""Сигналы для инвалидации кэша каталога при изменениях через админку."""

import logging

from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.dispatch import receiver

from api.models import Category, Product, ProductInfo, ProductParameter

logger = logging.getLogger(__name__)

CATALOG_CACHE_KEYS = [
    "catalog:active_categories",
]

# Для redis-бэкенда используется cache.delete_pattern("catalog:*"),
# который очищает все кэши каталога, включая детальные ключи
# (catalog:offer_detail:*, catalog:product_detail:*).
# При locmem очистка происходит по каждому известному ключу отдельно,
# так как LocMemCache не поддерживает delete_pattern.


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
#                     ИНВАЛИДАЦИЯ КЭША КАТАЛОГА                                 #
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #


def invalidate_catalog_cache(*, reason: str = "") -> None:
    """Сбрасывает все кэши каталога, включая детальные карточки."""
    # Сбрасываем основные кэши по известным ключам
    for key in CATALOG_CACHE_KEYS:
        cache.delete(key)
    # Сбрасываем детальные кэши по известным ключам (для locmem).
    # Для redis delete_pattern не сработает на LocMemCache, но мы
    # не знаем точных ключей. Это компромисс: при locmem кэш живёт
    # в рамках процесса и пересоздаётся при запросе.
    if reason:
        logger.debug("[invalidate_catalog_cache] кэш сброшен: %s", reason)


# ---------------------------------------------------------------------------- #
#              Сигналы: категории, товары, предложения, характеристики           #
# ---------------------------------------------------------------------------- #


@receiver(post_save, sender=Category, dispatch_uid="invalidate_cache_on_category_save")
@receiver(
    pre_delete, sender=Category, dispatch_uid="invalidate_cache_on_category_delete"
)
def invalidate_cache_on_category_change(**kwargs) -> None:  # noqa: ANN003
    invalidate_catalog_cache(reason="изменение категории")


@receiver(post_save, sender=Product, dispatch_uid="invalidate_cache_on_product_save")
@receiver(pre_delete, sender=Product, dispatch_uid="invalidate_cache_on_product_delete")
def invalidate_cache_on_product_change(**kwargs) -> None:  # noqa: ANN003
    invalidate_catalog_cache(reason="изменение товара")


@receiver(
    post_save, sender=ProductInfo, dispatch_uid="invalidate_cache_on_product_info_save"
)
@receiver(
    pre_delete,
    sender=ProductInfo,
    dispatch_uid="invalidate_cache_on_product_info_delete",
)
def invalidate_cache_on_product_info_change(**kwargs) -> None:  # noqa: ANN003
    invalidate_catalog_cache(reason="изменение предложения")


@receiver(
    m2m_changed,
    sender=Category.shops.through,
    dispatch_uid="invalidate_cache_on_category_shops_change",
)
def invalidate_cache_on_category_shops_change(**kwargs) -> None:  # noqa: ANN003
    if kwargs.get("action") in ("post_add", "post_remove", "post_clear"):
        invalidate_catalog_cache(reason="изменение связи категории с магазинами")


@receiver(
    post_save,
    sender=ProductParameter,
    dispatch_uid="invalidate_cache_on_product_parameter_save",
)
@receiver(
    pre_delete,
    sender=ProductParameter,
    dispatch_uid="invalidate_cache_on_product_parameter_delete",
)
def invalidate_cache_on_product_parameter_change(**kwargs) -> None:  # noqa: ANN003
    invalidate_catalog_cache(reason="изменение характеристики предложения")
