from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer

from .models import User


class UserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "password",
            "company",
            "position",
            "type",
        )
        extra_kwargs = {
            "company": {"required": False},
            "position": {"required": False},
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
