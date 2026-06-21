from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Contact, Order, OrderItem, Product, ProductInfo, User


# 1. Model ----
class UserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "password",
            "type",
        )
        extra_kwargs = {
            "type": {
                "required": False,
                "default": "buyer",
                "help_text": "Тип пользователя. По умолчанию создается покупатель.",
            },  # значение по умолчанию, если не передано
            "password": {
                "write_only": True,
                "help_text": "Пароль пользователя. В ответах API не возвращается.",
            },
        }


class UserSerializer(BaseUserSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "company",
            "position",
            "type",
            # "is_active",
        )


class ProductSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = Product
        fields = (
            "id",
            "category",
            "name",
        )
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID товара."},
            "category": {"help_text": "ID категории товара."},
            "name": {"help_text": "Название товара в каталоге."},
        }


class ProductInfoSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = ProductInfo
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID конкретного предложения."},
            "product": {"help_text": "ID товара из каталога."},
            "shop": {"help_text": "ID магазина, который продает товар."},
            "name": {"help_text": "Название предложения у магазина."},
            "quantity": {"help_text": "Количество товара в наличии."},
            "price": {"help_text": "Цена предложения."},
            "price_rrc": {"help_text": "Рекомендованная розничная цена."},
        }


class OrderSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = Order
        fields = ("id", "user", "dt", "state")
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID заказа."},
            "user": {"read_only": True, "help_text": "ID владельца заказа."},
            "dt": {"read_only": True, "help_text": "Дата и время создания заказа."},
            "state": {"help_text": "Текущий статус заказа."},
        }


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = OrderItem
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID позиции заказа."},
            "order": {"help_text": "ID заказа."},
            "product_info": {"help_text": "ID предложения товара."},
            "quantity": {"help_text": "Количество единиц товара в позиции."},
        }


class ContactSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True, help_text="ID адреса доставки.")

    class Meta(BaseUserSerializer.Meta):
        model = Contact
        fields = (
            "id",
            "city",
            "street",
            "house",
            "structure",
            "building",
            "apartment",
            "phone",
        )
        extra_kwargs = {
            "city": {"help_text": "Город доставки."},
            "street": {"help_text": "Улица доставки."},
            "house": {"help_text": "Дом. Может быть пустой строкой."},
            "structure": {"help_text": "Корпус. Может быть пустой строкой."},
            "building": {"help_text": "Строение. Может быть пустой строкой."},
            "apartment": {"help_text": "Квартира. Может быть пустой строкой."},
            "phone": {"help_text": "Телефон получателя."},
        }


# 2. Other ----
class AddToBasketSerializer(serializers.Serializer):
    product_info_id = serializers.IntegerField(
        help_text="ID предложения товара, которое нужно добавить в корзину."
    )
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Количество добавляемых единиц. Минимальное значение: 1.",
    )


class OrderConfirmSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        help_text="ID заказа в статусе basket, который нужно подтвердить."
    )
    contact_id = serializers.IntegerField(
        help_text="ID адреса доставки текущего пользователя."
    )


class OrderHistorySerializer(serializers.ModelSerializer):
    total_sum = serializers.SerializerMethodField(
        help_text="Итоговая сумма заказа: сумма quantity * price по всем позициям."
    )

    class Meta:
        model = Order
        fields = ("id", "dt", "total_sum", "state")

    @extend_schema_field(OpenApiTypes.INT)
    def get_total_sum(self, obj: Order) -> int:
        # вычисляем сумму заказа: сумма (quantity * price) для всех OrderItem
        total = 0
        for item in OrderItem.objects.filter(order=obj).select_related("product_info"):
            total += item.quantity * item.product_info.price
        return total


class OrderUpdateSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(
        choices=[
            "new",
        ],
        help_text="Новый статус заказа. Сейчас через API разрешен только переход в new.",
    )

    class Meta:
        model = Order
        fields = ["state"]


class PaginatedProductResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(
        read_only=True, help_text="Общее количество товаров."
    )
    next = serializers.URLField(
        allow_null=True,
        read_only=True,
        help_text="URL следующей страницы или null, если следующей страницы нет.",
    )
    previous = serializers.URLField(
        allow_null=True,
        read_only=True,
        help_text="URL предыдущей страницы или null, если предыдущей страницы нет.",
    )
    results = ProductSerializer(many=True, read_only=True)


class PaginatedOrderHistoryResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(
        read_only=True, help_text="Общее количество заказов."
    )
    next = serializers.URLField(
        allow_null=True,
        read_only=True,
        help_text="URL следующей страницы или null, если следующей страницы нет.",
    )
    previous = serializers.URLField(
        allow_null=True,
        read_only=True,
        help_text="URL предыдущей страницы или null, если предыдущей страницы нет.",
    )
    results = OrderHistorySerializer(many=True, read_only=True)


class BasketItemResponseSerializer(serializers.Serializer):
    data = OrderItemSerializer(read_only=True)


class ContactResponseSerializer(serializers.Serializer):
    data = ContactSerializer(read_only=True)


class ContactListResponseSerializer(serializers.Serializer):
    data = ContactSerializer(many=True, read_only=True)


class OrderConfirmResponseSerializer(serializers.Serializer):
    status = serializers.CharField(
        read_only=True,
        help_text="Статус выполнения операции. Успешное значение: Order confirmed.",
    )


class ErrorDetailSerializer(serializers.Serializer):
    detail = serializers.CharField(read_only=True, help_text="Описание ошибки.")
