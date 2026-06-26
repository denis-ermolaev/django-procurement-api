import logging
from typing import Any

from django.core.cache import cache
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from api.filters import OfferFilter, ProductFilter
from api.models import Category, Product, ProductInfo, User
from core.settings import CACHE_TIMEOUT_CATALOG

logger = logging.getLogger(__name__)


# 0. Справочники ----
def get_active_categories() -> list[Category]:
    """Возвращает активные категории, в которых есть активные предложения."""
    logger.debug("[get_active_categories] загрузка активных категорий")

    cache_key = "catalog:active_categories"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("[get_active_categories] возвращено из кэша")
        return cached

    qs = list(
        Category.objects.filter(
            status="active",
            shops__status="active",
            shops__is_accepting_orders=True,
            product__status="active",
            product__productinfo__status="active",
        )
        .distinct()
        .order_by("name")
    )
    cache.set(cache_key, qs, CACHE_TIMEOUT_CATALOG)
    logger.debug(
        "[get_active_categories] закэшировано на %s сек", CACHE_TIMEOUT_CATALOG
    )
    return qs


# 1. Каталог товаров ----
def get_filtered_products(user: User, query_params: Any) -> QuerySet[Product]:
    logger.debug(
        "[get_filtered_products] product_list_started user_id=%s filter_keys=%s",
        user.pk,
        sorted(query_params.keys()),
    )

    parameter = query_params.get("parameter")
    if parameter and ":" not in parameter:
        logger.warning(
            "[get_filtered_products] product_list_invalid_parameter_filter user_id=%s",
            user.pk,
        )
        raise ValidationError(
            {"parameter": ["Ожидаемый формат: имя_параметра:значение."]}
        )

    base_queryset = Product.objects.filter(
        status="active",
        category__status="active",
        productinfo__status="active",
        productinfo__shop__status="active",
        productinfo__shop__is_accepting_orders=True,
    ).order_by("id")
    filter_set = ProductFilter(query_params, queryset=base_queryset)
    if not filter_set.is_valid():
        logger.warning(
            "[get_filtered_products] product_list_invalid_filters user_id=%s errors=%s",
            user.pk,
            filter_set.errors,
        )
        raise ValidationError(filter_set.errors)

    return filter_set.qs.distinct()


def log_product_page_loaded(user: User, *, total_count: int, page_size: int) -> None:
    logger.debug(
        "[log_product_page_loaded] product_list_completed user_id=%s total_count=%s page_size=%s",
        user.pk,
        total_count,
        page_size,
    )


def get_product_info(pk: int) -> ProductInfo:
    cache_key = f"catalog:product_detail:{pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("[get_product_info] возвращено из кэша product_info_id=%s", pk)
        return cached

    product_info = get_object_or_404(
        ProductInfo,
        pk=pk,
        status="active",
        shop__status="active",
        shop__is_accepting_orders=True,
        product__status="active",
        product__category__status="active",
    )
    cache.set(cache_key, product_info, CACHE_TIMEOUT_CATALOG)
    logger.debug(
        "[get_product_info] product_detail_loaded product_info_id=%s product_id=%s shop_id=%s",
        product_info.pk,
        product_info.product.pk,
        product_info.shop.pk,
    )
    return product_info


# 2. Предложения ----
def get_available_offers(
    user: User,
    query_params: Any,
    *,
    product_id: int | None = None,
) -> QuerySet[ProductInfo]:
    logger.debug(
        "[get_available_offers] загрузка предложений user_id=%s product_id=%s filter_keys=%s",
        user.pk,
        product_id,
        sorted(query_params.keys()),
    )

    parameter = query_params.get("parameter")
    if parameter and ":" not in parameter:
        logger.warning(
            "[get_available_offers] некорректный фильтр parameter user_id=%s",
            user.pk,
        )
        raise ValidationError(
            {"parameter": ["Ожидаемый формат: имя_параметра:значение."]}
        )

    base_queryset = ProductInfo.objects.filter(
        status="active",
        shop__status="active",
        shop__is_accepting_orders=True,
        product__status="active",
        product__category__status="active",
    )
    if product_id is not None:
        get_object_or_404(
            Product,
            pk=product_id,
            status="active",
            category__status="active",
        )
        base_queryset = base_queryset.filter(product_id=product_id)

    filter_set = OfferFilter(
        query_params,
        queryset=base_queryset.select_related(
            "product__category", "shop"
        ).prefetch_related("productparameter_set__parameter"),
    )
    if not filter_set.is_valid():
        logger.warning(
            "[get_available_offers] некорректные фильтры user_id=%s errors=%s",
            user.pk,
            filter_set.errors,
        )
        raise ValidationError(filter_set.errors)

    return filter_set.qs.distinct().order_by("id")


def log_offer_page_loaded(
    user: User,
    *,
    total_count: int,
    page_size: int,
    product_id: int | None = None,
) -> None:
    logger.debug(
        "[log_offer_page_loaded] предложения загружены user_id=%s product_id=%s total_count=%s page_size=%s",
        user.pk,
        product_id,
        total_count,
        page_size,
    )


def get_offer(pk: int) -> ProductInfo:
    cache_key = f"catalog:offer_detail:{pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("[get_offer] возвращено из кэша offer_id=%s", pk)
        return cached

    offer = get_object_or_404(
        ProductInfo.objects.select_related(
            "product__category", "shop"
        ).prefetch_related("productparameter_set__parameter"),
        pk=pk,
        status="active",
        shop__status="active",
        shop__is_accepting_orders=True,
        product__status="active",
        product__category__status="active",
    )
    cache.set(cache_key, offer, CACHE_TIMEOUT_CATALOG)
    logger.debug(
        "[get_offer] предложение загружено offer_id=%s product_id=%s shop_id=%s",
        offer.pk,
        offer.product.pk,
        offer.shop.pk,
    )
    return offer
