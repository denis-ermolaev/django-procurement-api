from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from rest_framework import serializers

from .models import Contact, Order, OrderItem, Product, ProductInfo, User


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
        fields = ("id", "user", "dt", "status")


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = OrderItem
        fields = "__all__"


class AddToBasketSerializer(serializers.Serializer):
    product_info_id = serializers.IntegerField()
    order_id = serializers.IntegerField()
    quantity = serializers.IntegerField()


class ContactSerializer(serializers.ModelSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = Contact
        fields = "__all__"
