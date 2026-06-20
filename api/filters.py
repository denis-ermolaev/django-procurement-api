import django_filters

from .models import Product


class ProductFilter(django_filters.FilterSet):
    # Поиск по названию товара
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    # Фильтрация по категории
    category_id = django_filters.NumberFilter(field_name="category_id")

    # Фильтрация по магазину (товары, доступные в конкретном магазине)
    shop_id = django_filters.NumberFilter(
        field_name="productinfo__shop_id", distinct=True
    )

    # Диапазон цен (по предложениям)
    price_min = django_filters.NumberFilter(
        field_name="productinfo__price", lookup_expr="gte", distinct=True
    )
    price_max = django_filters.NumberFilter(
        field_name="productinfo__price", lookup_expr="lte", distinct=True
    )

    # Фильтрация по характеристикам (параметрам)
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
