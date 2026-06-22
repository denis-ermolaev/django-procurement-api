import logging
from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from api.filters import ProductFilter
from api.models import Product, ProductInfo, User

logger = logging.getLogger(__name__)


# 1. Каталог товаров ----
def get_filtered_products(user: User, query_params: Any) -> QuerySet[Product]:
    logger.debug(
        "product_list_started user_id=%s filter_keys=%s",
        user.pk,
        sorted(query_params.keys()),
    )

    parameter = query_params.get("parameter")
    if parameter and ":" not in parameter:
        logger.warning(
            "product_list_invalid_parameter_filter user_id=%s",
            user.pk,
        )
        raise ValidationError(
            {"parameter": ["Ожидаемый формат: имя_параметра:значение."]}
        )

    filter_set = ProductFilter(query_params, queryset=Product.objects.order_by("id"))
    if not filter_set.is_valid():
        logger.warning(
            "product_list_invalid_filters user_id=%s errors=%s",
            user.pk,
            filter_set.errors,
        )
        raise ValidationError(filter_set.errors)

    return filter_set.qs


def log_product_page_loaded(user: User, *, total_count: int, page_size: int) -> None:
    logger.debug(
        "product_list_completed user_id=%s total_count=%s page_size=%s",
        user.pk,
        total_count,
        page_size,
    )


def get_product_info(pk: int) -> ProductInfo:
    product_info = get_object_or_404(ProductInfo, pk=pk)
    logger.debug(
        "product_detail_loaded product_info_id=%s product_id=%s shop_id=%s",
        product_info.pk,
        product_info.product.pk,
        product_info.shop.pk,
    )
    return product_info
