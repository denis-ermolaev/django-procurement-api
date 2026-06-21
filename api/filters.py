import django_filters

from .models import Product


# 1. Фильтры каталога ----
class ProductFilter(django_filters.FilterSet):
    ## 1.1. Поиск и прямые фильтры ----
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    category_id = django_filters.NumberFilter(field_name="category_id")

    ## 1.2. Фильтры по связанным предложениям ----
    shop_id = django_filters.NumberFilter(
        field_name="productinfo__shop_id", distinct=True
    )
    price_min = django_filters.NumberFilter(
        field_name="productinfo__price", lookup_expr="gte", distinct=True
    )
    price_max = django_filters.NumberFilter(
        field_name="productinfo__price", lookup_expr="lte", distinct=True
    )

    ## 1.3. Фильтр по характеристикам ----
    parameter = django_filters.CharFilter(method="filter_by_parameter")

    class Meta:
        model = Product
        fields = [
            "search",
            "category_id",
            "shop_id",
            "price_min",
            "price_max",
            "parameter",
        ]

    def filter_by_parameter(self, queryset, _, value):
        """
        Ожидается строка вида 'имя_параметра:значение'
        Например: 'цвет:красный'
        """
        if ":" not in value:
            return queryset
        param_name, param_value = value.split(":", 1)
        return queryset.filter(
            productinfo__productparameter__parameter__name=param_name,
            productinfo__productparameter__value__icontains=param_value,
        ).distinct()
