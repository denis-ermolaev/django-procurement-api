import django_filters

from .models import Product


# 1. Фильтры каталога ----
class ProductFilter(django_filters.FilterSet):
    ## 1.1. Поиск и прямые фильтры ----
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    category_id = django_filters.NumberFilter(field_name="category_id")

    ## 1.2. Фильтры по связанным предложениям ----
    shop_id = django_filters.NumberFilter(method="filter_by_offer")
    price_min = django_filters.NumberFilter(method="filter_by_offer")
    price_max = django_filters.NumberFilter(method="filter_by_offer")

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

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)

        offer_filters = {}
        shop_id = self.form.cleaned_data.get("shop_id")
        price_min = self.form.cleaned_data.get("price_min")
        price_max = self.form.cleaned_data.get("price_max")
        parameter = self.form.cleaned_data.get("parameter")

        if shop_id is not None:
            offer_filters["productinfo__shop_id"] = shop_id
        if price_min is not None:
            offer_filters["productinfo__price__gte"] = price_min
        if price_max is not None:
            offer_filters["productinfo__price__lte"] = price_max
        if parameter and ":" in parameter:
            param_name, param_value = parameter.split(":", 1)
            offer_filters["productinfo__productparameter__parameter__name"] = param_name
            offer_filters["productinfo__productparameter__value__icontains"] = (
                param_value
            )

        if offer_filters:
            queryset = queryset.filter(**offer_filters).distinct()
        return queryset

    def filter_by_offer(self, queryset, _, value):
        return queryset

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
