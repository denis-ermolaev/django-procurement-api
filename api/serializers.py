from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
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
            },  # значение по умолчанию, если не передано
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


class ProductInfoSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = ProductInfo
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = Order
        fields = ("id", "user", "dt", "state")


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = OrderItem
        fields = "__all__"


class ContactSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

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


# 2. Other ----
class AddToBasketSerializer(serializers.Serializer):
    product_info_id = serializers.IntegerField()
    quantity = serializers.IntegerField()


class OrderConfirmSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    contact_id = serializers.IntegerField()


class OrderHistorySerializer(serializers.ModelSerializer):
    total_sum = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ("id", "dt", "total_sum", "state")

    def get_total_sum(self, obj):
        # вычисляем сумму заказа: сумма (quantity * price) для всех OrderItem
        total = 0
        for item in obj.orderitem_set.select_related("product_info"):
            total += item.quantity * item.product_info.price
        return total


class OrderUpdateSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(
        choices=[
            "new",
        ]
    )

    class Meta:
        model = Order
        fields = ["state"]
