from django.contrib import admin

from .models import (
    Category,
    Contact,
    ImportJob,
    Order,
    OrderItem,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status", "owner", "url", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "owner__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status")
    list_filter = ("status",)
    filter_horizontal = ("shops",)  # для ManyToMany


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "status")
    list_filter = ("category", "status")
    search_fields = ("name",)


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "shop",
        "name",
        "price",
        "quantity",
        "reserved_quantity",
        "status",
    )
    list_filter = ("shop", "product__category", "status")
    search_fields = ("product__name", "name")


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    list_display = ("id", "product_info", "parameter", "value")
    list_filter = ("parameter",)
    search_fields = ("value", "parameter__name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "state", "contact", "dt")
    list_filter = ("state", "dt")
    search_fields = ("user__email",)
    readonly_fields = ("dt",)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_info", "quantity", "state")
    list_filter = ("order__state", "state")
    search_fields = ("order__id", "product_info__name")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "city", "street", "phone", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("user__email", "phone")


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "status", "created_at", "completed_at")
    list_filter = ("status", "shop")
    readonly_fields = ("created_at", "completed_at")
