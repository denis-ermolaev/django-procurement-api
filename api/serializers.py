from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer

from .models import User


class CustomUserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ("email", "password", "company", "position", "type")
        extra_kwargs = {
            "company": {"required": False},
            "position": {"required": False},
            "type": {
                "required": False,
                "default": "buyer",
            },  # значение по умолчанию, если не передано
        }
