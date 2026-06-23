from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from djoser.serializers import UserSerializer as BaseUserSerializer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    ORDER_ITEM_STATE_CHOICES,
    PRODUCT_INFO_STATUS_CHOICES,
    STATE_CHOICES,
    Category,
    Contact,
    Order,
    OrderItem,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)

# 1. Константы сериализаторов ----
ORDER_UPDATE_STATE_CHOICES = tuple(
    (state, label) for state, label in STATE_CHOICES if state != "basket"
)
BUYER_ORDER_UPDATE_STATE_CHOICES = (("canceled", "Отменен"),)
SHOP_OFFER_STATUS_CHOICES = tuple(
    (state, label)
    for state, label in PRODUCT_INFO_STATUS_CHOICES
    if state in {"active", "hidden", "archived"}
)
SHOP_ORDER_ITEM_STATE_CHOICES = tuple(
    (state, label)
    for state, label in ORDER_ITEM_STATE_CHOICES
    if state in {"accepted", "assembled", "sent", "delivered", "canceled"}
)
ADMIN_ORDER_ITEM_STATE_CHOICES = tuple(
    (state, label) for state, label in ORDER_ITEM_STATE_CHOICES if state != "basket"
)


# 2. Сериализаторы пользователей ----
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
                "read_only": True,
                "help_text": "Тип пользователя. Обычная регистрация всегда создает покупателя.",
            },
            "password": {
                "write_only": True,
                "help_text": "Пароль пользователя. В ответах API не возвращается.",
            },
        }

    def validate(self, attrs):
        requested_type = self.initial_data.get("type")
        if requested_type not in (None, "", "buyer"):
            raise serializers.ValidationError(
                {
                    "type": (
                        "Через обычную регистрацию можно создать только покупателя. "
                        "Для магазина используйте /api/shops/register/."
                    )
                }
            )
        return super().validate(attrs)


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
        )


# 3. Сериализаторы магазинов ----
class RegisteredShopUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "type", "is_active")
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID пользователя магазина."},
            "email": {"read_only": True, "help_text": "Email пользователя магазина."},
            "first_name": {"read_only": True},
            "last_name": {"read_only": True},
            "type": {"read_only": True, "help_text": "Тип пользователя: shop."},
            "is_active": {
                "read_only": True,
                "help_text": "Активирован ли пользователь для получения JWT.",
            },
        }


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = (
            "id",
            "name",
            "url",
            "owner",
            "status",
            "is_accepting_orders",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID магазина."},
            "name": {"help_text": "Название магазина."},
            "url": {"help_text": "URL магазина. Может быть пустой строкой."},
            "owner": {"read_only": True, "help_text": "ID пользователя-владельца."},
            "status": {"read_only": True, "help_text": "Статус модерации магазина."},
            "is_accepting_orders": {"help_text": "Принимает ли магазин новые заказы."},
            "created_at": {
                "read_only": True,
                "help_text": "Дата и время создания магазина.",
            },
            "updated_at": {
                "read_only": True,
                "help_text": "Дата и время последнего обновления магазина.",
            },
        }


class ShopRegistrationSerializer(serializers.Serializer):
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
        help_text="Имя пользователя магазина.",
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
        help_text="Фамилия пользователя магазина.",
    )
    email = serializers.EmailField(help_text="Email пользователя магазина.")
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        help_text="Пароль пользователя магазина. В ответе не возвращается.",
    )
    shop_name = serializers.CharField(max_length=150, help_text="Название магазина.")
    url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="URL магазина. Может быть пустой строкой.",
    )

    def validate_email(self, value: str) -> str:
        email = User.objects.normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                "Пользователь с таким email уже существует."
            )
        return email

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class ShopRegistrationResponseSerializer(serializers.Serializer):
    user = RegisteredShopUserSerializer(read_only=True)
    shop = ShopSerializer(read_only=True)


# 4. Сериализаторы каталога ----
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "status")
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID категории."},
            "name": {"help_text": "Название категории."},
            "status": {"help_text": "Статус категории."},
        }


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id",
            "category",
            "name",
            "status",
        )
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID товара."},
            "category": {"help_text": "ID категории товара."},
            "name": {"help_text": "Название товара в каталоге."},
            "status": {"help_text": "Статус товара."},
        }


class ProductInfoSerializer(serializers.ModelSerializer):
    available_quantity = serializers.SerializerMethodField(
        help_text="Доступный к продаже остаток с учетом резерва."
    )

    class Meta:
        model = ProductInfo
        fields = (
            "id",
            "product",
            "shop",
            "external_id",
            "model",
            "name",
            "quantity",
            "available_quantity",
            "price",
            "price_rrc",
            "status",
        )
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID конкретного предложения."},
            "product": {"help_text": "ID товара Product из общего каталога."},
            "shop": {"help_text": "ID магазина, который продает это предложение."},
            "external_id": {"help_text": "Стабильный ID предложения в прайсе."},
            "model": {"help_text": "Модель или артикул предложения."},
            "name": {"help_text": "Название предложения в прайсе магазина."},
            "quantity": {
                "help_text": "Доступный остаток. При добавлении в корзину quantity не может быть больше этого значения."
            },
            "price": {"help_text": "Фактическая цена предложения."},
            "price_rrc": {"help_text": "Рекомендованная розничная цена."},
            "status": {"help_text": "Статус предложения."},
        }

    @extend_schema_field(OpenApiTypes.INT)
    def get_available_quantity(self, obj: ProductInfo) -> int:
        return max(obj.quantity - obj.reserved_quantity, 0)


class OfferParameterSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True, help_text="Название характеристики.")
    value = serializers.CharField(read_only=True, help_text="Значение характеристики.")


class BuyerOfferSerializer(serializers.ModelSerializer):
    offer_id = serializers.IntegerField(
        source="id",
        read_only=True,
        help_text="ID предложения ProductInfo.",
    )
    product_id = serializers.IntegerField(
        source="product.id",
        read_only=True,
        help_text="ID общего товара Product.",
    )
    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
        help_text="Название общего товара.",
    )
    offer_name = serializers.CharField(
        source="name",
        read_only=True,
        help_text="Название предложения в прайсе магазина.",
    )
    shop_id = serializers.IntegerField(
        source="shop.id",
        read_only=True,
        help_text="ID магазина.",
    )
    shop_name = serializers.CharField(
        source="shop.name",
        read_only=True,
        help_text="Название магазина.",
    )
    model = serializers.CharField(read_only=True, help_text="Модель или артикул.")
    available_quantity = serializers.SerializerMethodField(
        help_text="Доступный к покупке остаток: quantity - reserved_quantity."
    )
    parameters = serializers.SerializerMethodField(
        help_text="Характеристики конкретного предложения."
    )
    can_add_to_basket = serializers.SerializerMethodField(
        help_text="Можно ли добавить предложение в корзину покупателя."
    )

    class Meta:
        model = ProductInfo
        fields = (
            "id",
            "offer_id",
            "product_id",
            "product_name",
            "offer_name",
            "shop_id",
            "shop_name",
            "model",
            "quantity",
            "available_quantity",
            "price",
            "price_rrc",
            "status",
            "parameters",
            "can_add_to_basket",
        )

    @extend_schema_field(OpenApiTypes.INT)
    def get_available_quantity(self, obj: ProductInfo) -> int:
        return max(obj.quantity - obj.reserved_quantity, 0)

    @extend_schema_field(OfferParameterSerializer(many=True))
    def get_parameters(self, obj: ProductInfo) -> list[dict[str, str]]:
        parameters: list[ProductParameter] = list(
            ProductParameter.objects.filter(product_info=obj)
            .select_related("parameter")
            .order_by(
                "parameter__name",
            )
        )
        return [
            {"name": item.parameter.name, "value": item.value} for item in parameters
        ]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_add_to_basket(self, obj: ProductInfo) -> bool:
        return (
            obj.status == "active"
            and obj.shop.status == "active"
            and obj.shop.is_accepting_orders
            and obj.product.status == "active"
            and obj.product.category.status == "active"
            and self.get_available_quantity(obj) > 0
        )


class OfferSerializer(serializers.ModelSerializer):
    available_quantity = serializers.SerializerMethodField(
        help_text="Доступный остаток: quantity - reserved_quantity."
    )

    class Meta:
        model = ProductInfo
        fields = (
            "id",
            "product",
            "shop",
            "external_id",
            "model",
            "name",
            "quantity",
            "reserved_quantity",
            "available_quantity",
            "price",
            "price_rrc",
            "status",
            "updated_at",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "shop": {"read_only": True},
            "reserved_quantity": {"read_only": True},
            "updated_at": {"read_only": True},
            "status": {"help_text": "Статус предложения магазина."},
        }

    @extend_schema_field(OpenApiTypes.INT)
    def get_available_quantity(self, obj: ProductInfo) -> int:
        return max(obj.quantity - obj.reserved_quantity, 0)


class ShopOfferCreateSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(
        min_value=0,
        error_messages={"min_value": "Остаток не может быть отрицательным."},
    )
    price = serializers.IntegerField(
        min_value=1,
        error_messages={"min_value": "Цена должна быть больше 0."},
    )
    price_rrc = serializers.IntegerField(
        min_value=0,
        error_messages={
            "min_value": "Рекомендованная цена не может быть отрицательной."
        },
    )

    class Meta:
        model = ProductInfo
        fields = (
            "product",
            "external_id",
            "model",
            "name",
            "quantity",
            "price",
            "price_rrc",
            "status",
        )
        extra_kwargs = {
            "external_id": {"required": False, "allow_blank": True},
            "model": {"required": False, "allow_blank": True},
            "status": {
                "required": False,
                "help_text": "Статус предложения. По умолчанию active.",
            },
        }

    def validate_status(self, value: str) -> str:
        allowed_statuses = {status for status, _ in SHOP_OFFER_STATUS_CHOICES}
        if value not in allowed_statuses:
            raise serializers.ValidationError(
                "Магазин может использовать только active, hidden или archived."
            )
        return value

    def validate(self, attrs):
        if attrs["price"] <= 0:
            raise serializers.ValidationError({"price": "Цена должна быть больше 0."})
        if attrs.get("price_rrc", 0) < 0:
            raise serializers.ValidationError(
                {"price_rrc": "Рекомендованная цена не может быть отрицательной."}
            )
        if attrs["quantity"] < 0:
            raise serializers.ValidationError(
                {"quantity": "Остаток не может быть отрицательным."}
            )
        return attrs


class ShopOfferUpdateSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(
        min_value=0,
        required=False,
        error_messages={"min_value": "Остаток не может быть отрицательным."},
    )
    price = serializers.IntegerField(
        min_value=1,
        required=False,
        error_messages={"min_value": "Цена должна быть больше 0."},
    )
    price_rrc = serializers.IntegerField(
        min_value=0,
        required=False,
        error_messages={
            "min_value": "Рекомендованная цена не может быть отрицательной."
        },
    )
    status = serializers.ChoiceField(
        choices=SHOP_OFFER_STATUS_CHOICES,
        required=False,
        help_text="Статус предложения: active, hidden или archived.",
    )

    class Meta:
        model = ProductInfo
        fields = (
            "external_id",
            "model",
            "name",
            "quantity",
            "price",
            "price_rrc",
            "status",
        )
        extra_kwargs = {
            "external_id": {"required": False, "allow_blank": True},
            "model": {"required": False, "allow_blank": True},
            "name": {"required": False},
            "quantity": {"required": False},
            "price": {"required": False},
            "price_rrc": {"required": False},
        }

    def validate(self, attrs):
        if "price" in attrs and attrs["price"] <= 0:
            raise serializers.ValidationError({"price": "Цена должна быть больше 0."})
        if "price_rrc" in attrs and attrs["price_rrc"] < 0:
            raise serializers.ValidationError(
                {"price_rrc": "Рекомендованная цена не может быть отрицательной."}
            )
        if "quantity" in attrs and attrs["quantity"] < 0:
            raise serializers.ValidationError(
                {"quantity": "Остаток не может быть отрицательным."}
            )
        return attrs


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = ("id", "name")
        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"help_text": "Название характеристики."},
        }


# 5. Сериализаторы заказов ----
class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "id",
            "user",
            "dt",
            "confirmed_at",
            "state",
            "cancellation_reason",
        )
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID заказа."},
            "user": {"read_only": True, "help_text": "ID владельца заказа."},
            "dt": {"read_only": True, "help_text": "Дата и время создания заказа."},
            "confirmed_at": {
                "read_only": True,
                "help_text": "Дата и время подтверждения заказа.",
            },
            "state": {"help_text": "Текущий статус заказа."},
            "cancellation_reason": {
                "read_only": True,
                "help_text": "Административная причина отмены заказа.",
            },
        }


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID позиции заказа."},
            "order": {"help_text": "ID заказа, к которому относится позиция."},
            "product_info": {"help_text": "ID предложения товара."},
            "quantity": {
                "help_text": "Количество единиц этого предложения внутри заказа."
            },
            "state": {"help_text": "Статус позиции заказа."},
        }


class OrderDetailSerializer(serializers.ModelSerializer):
    contact = serializers.PrimaryKeyRelatedField(
        read_only=True,
        allow_null=True,
        help_text="ID адреса доставки. До подтверждения заказа может быть null.",
    )
    items = OrderItemSerializer(
        source="orderitem_set",
        many=True,
        read_only=True,
        help_text="Позиции заказа.",
    )
    total_sum = serializers.SerializerMethodField(
        help_text="Итоговая сумма заказа: сумма quantity * price по всем позициям."
    )

    class Meta:
        model = Order
        fields = (
            "id",
            "user",
            "dt",
            "confirmed_at",
            "state",
            "contact",
            "cancellation_reason",
            "total_sum",
            "items",
        )
        extra_kwargs = {
            "id": {"read_only": True, "help_text": "ID заказа."},
            "user": {"read_only": True, "help_text": "ID владельца заказа."},
            "dt": {"read_only": True, "help_text": "Дата и время создания заказа."},
            "confirmed_at": {
                "read_only": True,
                "help_text": "Дата и время подтверждения заказа.",
            },
            "state": {"help_text": "Текущий статус заказа."},
        }

    @extend_schema_field(OpenApiTypes.INT)
    def get_total_sum(self, obj: Order) -> int:
        total = 0
        for item in OrderItem.objects.filter(order=obj).select_related("product_info"):
            unit_price = item.unit_price or item.product_info.price
            total += item.quantity * unit_price
        return total


# 6. Сериализаторы контактов ----
class ContactSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True, help_text="ID адреса доставки.")

    class Meta:
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


# 7. Сериализаторы входных команд ----
class AddToBasketSerializer(serializers.Serializer):
    offer_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="ID предложения Offer/ProductInfo, которое нужно добавить в корзину.",
    )
    product_info_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Legacy alias для offer_id.",
    )
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Количество добавляемых единиц. Минимальное значение: 1.",
    )

    def validate(self, attrs):
        if not attrs.get("offer_id") and not attrs.get("product_info_id"):
            raise serializers.ValidationError({"offer_id": "Передайте offer_id."})
        attrs["offer_id"] = attrs.get("offer_id") or attrs["product_info_id"]
        return attrs


class UpdateBasketItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Новое количество позиции корзины.",
    )


class DeleteBasketItemSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Опциональный ID заказа-корзины для дополнительной проверки.",
    )
    item_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="ID позиции корзины OrderItem, которую нужно удалить.",
    )
    product_info_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text="Устаревшее имя параметра. Временно принимается как item_id для обратной совместимости.",
    )

    def validate(self, attrs):
        if not attrs.get("item_id") and not attrs.get("product_info_id"):
            raise serializers.ValidationError(
                {"item_id": "Передайте item_id позиции корзины."}
            )
        return attrs


class OrderConfirmSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(
        min_value=1, help_text="ID заказа в статусе basket, который нужно подтвердить."
    )
    contact_id = serializers.IntegerField(
        min_value=1, help_text="ID адреса доставки текущего пользователя."
    )


class OrderHistorySerializer(serializers.ModelSerializer):
    total_sum = serializers.SerializerMethodField(
        help_text="Итоговая сумма заказа: сумма quantity * price по всем позициям."
    )

    class Meta:
        model = Order
        fields = ("id", "dt", "confirmed_at", "total_sum", "state")

    @extend_schema_field(OpenApiTypes.INT)
    def get_total_sum(self, obj: Order) -> int:
        total = 0
        for item in OrderItem.objects.filter(order=obj).select_related("product_info"):
            unit_price = item.unit_price or item.product_info.price
            total += item.quantity * unit_price
        return total


class OrderUpdateSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(
        choices=BUYER_ORDER_UPDATE_STATE_CHOICES,
        help_text="Покупатель может только отменить заказ до начала обработки.",
    )

    class Meta:
        model = Order
        fields = ["state"]


class AdminOrderUpdateSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(
        choices=ORDER_UPDATE_STATE_CHOICES,
        required=False,
        help_text="Новый административный статус заказа. Статус basket запрещен.",
    )
    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Обязательная причина при административной отмене заказа.",
    )

    class Meta:
        model = Order
        fields = ("state", "cancellation_reason")

    def validate(self, attrs):
        if attrs.get("state") == "canceled" and not attrs.get("cancellation_reason"):
            raise serializers.ValidationError(
                {"cancellation_reason": "Укажите причину отмены заказа."}
            )
        return attrs


class ShopOrderItemUpdateSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(
        choices=SHOP_ORDER_ITEM_STATE_CHOICES,
        help_text="Новый статус позиции заказа.",
    )

    class Meta:
        model = OrderItem
        fields = ["state"]


class AdminOrderItemUpdateSerializer(serializers.ModelSerializer):
    state = serializers.ChoiceField(
        choices=ADMIN_ORDER_ITEM_STATE_CHOICES,
        help_text="Новый административный статус позиции заказа.",
    )

    class Meta:
        model = OrderItem
        fields = ["state"]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("is_active", "type", "is_staff")
        extra_kwargs = {
            "is_active": {"required": False},
            "type": {"required": False},
            "is_staff": {"required": False},
        }

    def validate(self, attrs):
        user_type = attrs.get("type", getattr(self.instance, "type", None))
        is_staff = attrs.get("is_staff", getattr(self.instance, "is_staff", False))
        if user_type == "admin" and not is_staff:
            raise serializers.ValidationError(
                {"is_staff": "Пользователь с ролью admin должен иметь is_staff=True."}
            )
        return attrs


class AdminShopUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ("name", "url", "status", "is_accepting_orders")
        extra_kwargs = {
            "name": {"required": False},
            "url": {"required": False},
            "status": {"required": False},
            "is_accepting_orders": {"required": False},
        }


class AdminOfferUpdateSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(
        min_value=0,
        required=False,
        error_messages={"min_value": "Остаток не может быть отрицательным."},
    )
    price = serializers.IntegerField(
        min_value=1,
        required=False,
        error_messages={"min_value": "Цена должна быть больше 0."},
    )
    price_rrc = serializers.IntegerField(
        min_value=0,
        required=False,
        error_messages={
            "min_value": "Рекомендованная цена не может быть отрицательной."
        },
    )

    class Meta:
        model = ProductInfo
        fields = (
            "external_id",
            "model",
            "name",
            "quantity",
            "price",
            "price_rrc",
            "status",
        )
        extra_kwargs = {
            "external_id": {"required": False, "allow_blank": True},
            "model": {"required": False, "allow_blank": True},
            "name": {"required": False},
            "quantity": {"required": False},
            "price": {"required": False},
            "price_rrc": {"required": False},
            "status": {"required": False},
        }

    def validate(self, attrs):
        if "price" in attrs and attrs["price"] <= 0:
            raise serializers.ValidationError({"price": "Цена должна быть больше 0."})
        if "price_rrc" in attrs and attrs["price_rrc"] < 0:
            raise serializers.ValidationError(
                {"price_rrc": "Рекомендованная цена не может быть отрицательной."}
            )
        if "quantity" in attrs and attrs["quantity"] < 0:
            raise serializers.ValidationError(
                {"quantity": "Остаток не может быть отрицательным."}
            )
        return attrs


# 8. Сериализаторы ответов ----
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


class PaginatedBuyerOfferResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(
        read_only=True, help_text="Общее количество предложений."
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
    results = BuyerOfferSerializer(many=True, read_only=True)


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


class BasketItemSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True, help_text="ID позиции корзины.")
    offer_id = serializers.IntegerField(read_only=True, help_text="ID предложения.")
    product_name = serializers.CharField(read_only=True, help_text="Название товара.")
    offer_name = serializers.CharField(
        read_only=True, help_text="Название предложения."
    )
    shop_name = serializers.CharField(read_only=True, help_text="Название магазина.")
    unit_price = serializers.IntegerField(read_only=True, help_text="Текущая цена.")
    quantity = serializers.IntegerField(read_only=True, help_text="Количество.")
    line_total = serializers.IntegerField(read_only=True, help_text="Сумма позиции.")
    available_quantity = serializers.IntegerField(
        read_only=True, help_text="Доступный остаток."
    )
    state = serializers.CharField(read_only=True, help_text="Статус позиции.")
    warnings = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
        help_text="Предупреждения о недоступности позиции.",
    )
    is_available = serializers.BooleanField(
        read_only=True, help_text="Можно ли оформить позицию."
    )


class BasketSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        allow_null=True,
        read_only=True,
        help_text="ID заказа-корзины или null, если корзина еще не создана.",
    )
    state = serializers.CharField(read_only=True, help_text="Статус корзины.")
    items = BasketItemSummarySerializer(many=True, read_only=True)
    total = serializers.IntegerField(read_only=True, help_text="Итоговая сумма.")


class BasketItemResponseSerializer(serializers.Serializer):
    data = BasketItemSummarySerializer(read_only=True)


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


class ShopImportSerializer(serializers.Serializer):
    file = serializers.FileField(
        required=False,
        help_text="YAML-файл прайса магазина.",
    )
    content = serializers.CharField(
        required=False,
        allow_blank=False,
        help_text="YAML-содержимое прайса, если файл не передается multipart-запросом.",
    )

    def validate(self, attrs):
        if not attrs.get("file") and not attrs.get("content"):
            raise serializers.ValidationError(
                {"file": "Передайте YAML-файл или поле content."}
            )
        return attrs


class ShopImportResultSerializer(serializers.Serializer):
    loaded_count = serializers.IntegerField(read_only=True)
    skipped_count = serializers.IntegerField(read_only=True)
    created_products = serializers.IntegerField(read_only=True)
    updated_products = serializers.IntegerField(read_only=True)
    created_offers = serializers.IntegerField(read_only=True)
    updated_offers = serializers.IntegerField(read_only=True)
    hidden_offers = serializers.IntegerField(read_only=True)
    parameter_count = serializers.IntegerField(read_only=True)
