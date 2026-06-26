from typing import Any, ClassVar, cast

import django_stubs_ext
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

django_stubs_ext.monkeypatch()


# 1. Константы ----
STATE_CHOICES = (
    ("basket", "Статус корзины"),
    ("confirmed", "Подтвержден"),
    ("processing", "В обработке"),
    ("sent", "Отправлен"),
    ("delivered", "Доставлен"),
    ("partially_canceled", "Частично отменен"),
    ("canceled", "Отменен"),
)

ORDER_ITEM_STATE_CHOICES = (
    ("basket", "В корзине"),
    ("confirmed", "Подтверждена"),
    ("accepted", "Принята магазином"),
    ("assembled", "Собрана"),
    ("sent", "Отправлена"),
    ("delivered", "Доставлена"),
    ("canceled", "Отменена"),
)

ARCHIVE_STATUS_CHOICES = (
    ("active", "Активен"),
    ("archived", "Архивирован"),
)

PRODUCT_INFO_STATUS_CHOICES = (
    ("active", "Активно"),
    ("hidden", "Скрыто"),
    ("archived", "Архивировано"),
    ("blocked", "Заблокировано"),
)

USER_TYPE_CHOICES = (
    ("shop", "Магазин"),
    ("buyer", "Покупатель"),
    ("admin", "Администратор"),
)

SHOP_STATUS_CHOICES = (
    ("pending", "Ожидает проверки"),
    ("active", "Активен"),
    ("blocked", "Заблокирован"),
    ("archived", "Архивирован"),
)

IMPORT_JOB_STATUS_CHOICES = (
    ("pending", "Ожидает"),
    ("processing", "В обработке"),
    ("completed", "Завершён"),
    ("failed", "Ошибка"),
)


# 2. Модели авторизации ----
class UserManager(BaseUserManager):
    """Менеджер пользователей с email в качестве логина."""

    use_in_migrations = True

    def _create_user(
        self, email: str, password: str | None, **extra_fields: Any
    ) -> "User":
        """Создать пользователя с нормализованным email и сохраненным паролем."""
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return cast("User", user)

    def create_user(  # type: ignore[override]
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(  # type: ignore[override]
        self, email: str, password: str, **extra_fields: Any
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("type", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("type") != "admin":
            raise ValueError("Superuser must have type='admin'.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Пользователь с авторизацией по уникальному email."""

    REQUIRED_FIELDS = []
    objects: ClassVar[UserManager] = UserManager()
    USERNAME_FIELD = "email"
    email = models.EmailField(_("email address"), unique=True)
    company = models.CharField(verbose_name="Компания", max_length=40, blank=True)
    position = models.CharField(verbose_name="Должность", max_length=40, blank=True)

    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _("username"),
        max_length=150,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[username_validator],
        unique=False,
        blank=True,
        default="",
    )
    is_active = models.BooleanField(
        _("active"),
        default=False,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    type = models.CharField(
        verbose_name="Тип пользователя",
        choices=USER_TYPE_CHOICES,
        max_length=5,
        default="buyer",
    )

    def __str__(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Список пользователей"
        ordering = ("email",)


# 3. Модели api ----
class Shop(models.Model):
    owner = models.OneToOneField(
        User,
        verbose_name="Владелец",
        related_name="shop",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=150)
    url = models.URLField(blank=True)
    status = models.CharField(
        verbose_name="Статус",
        choices=SHOP_STATUS_CHOICES,
        max_length=10,
        default="pending",
    )
    is_accepting_orders = models.BooleanField(
        verbose_name="Принимает заказы",
        default=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
        ordering = ("id",)


class Category(models.Model):
    shops = models.ManyToManyField(Shop)
    name = models.CharField(max_length=150)
    status = models.CharField(
        verbose_name="Статус",
        choices=ARCHIVE_STATUS_CHOICES,
        max_length=10,
        default="active",
    )

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    status = models.CharField(
        verbose_name="Статус",
        choices=ARCHIVE_STATUS_CHOICES,
        max_length=10,
        default="active",
    )

    def __str__(self) -> str:
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=100, blank=True, db_index=True)
    model = models.CharField(max_length=150, blank=True)
    name = models.CharField(max_length=150)
    quantity = models.IntegerField()
    reserved_quantity = models.PositiveIntegerField(default=0)
    price = models.IntegerField()
    price_rrc = models.IntegerField()
    status = models.CharField(
        verbose_name="Статус",
        choices=PRODUCT_INFO_STATUS_CHOICES,
        max_length=10,
        default="active",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.shop})"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="product_info_quantity_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__gte=0),
                name="product_info_reserved_quantity_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__lte=models.F("quantity")),
                name="product_info_reserved_lte_quantity",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="product_info_price_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(price_rrc__gte=0),
                name="product_info_price_rrc_gte_0",
            ),
            models.UniqueConstraint(
                fields=["shop", "external_id"],
                condition=~models.Q(external_id=""),
                name="unique_offer_shop_external_id",
            ),
        ]


class Parameter(models.Model):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self) -> str:
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE)
    value = models.CharField(max_length=200)

    def __str__(self) -> str:
        return f"{self.parameter}: {self.value}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product_info", "parameter"],
                name="unique_product_parameter_per_offer",
            ),
        ]


class Contact(models.Model):
    user = models.ForeignKey(
        User,
        verbose_name="Пользователь",
        related_name="contacts",
        blank=True,
        on_delete=models.CASCADE,
    )

    city = models.CharField(max_length=50, verbose_name="Город")
    street = models.CharField(max_length=100, verbose_name="Улица")
    house = models.CharField(max_length=15, verbose_name="Дом", blank=True)
    structure = models.CharField(max_length=15, verbose_name="Корпус", blank=True)
    building = models.CharField(max_length=15, verbose_name="Строение", blank=True)
    apartment = models.CharField(max_length=15, verbose_name="Квартира", blank=True)
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    is_deleted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.city}, {self.street}, {self.phone}"


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    dt = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    state = models.CharField(
        verbose_name="Статус", choices=STATE_CHOICES, max_length=20
    )
    contact = models.ForeignKey(
        Contact, verbose_name="Контакт", blank=True, null=True, on_delete=models.CASCADE
    )
    cancellation_reason = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Order #{self.pk} ({self.state})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(state="basket"),
                name="unique_active_basket_per_user",
            ),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product_info = models.ForeignKey(
        ProductInfo,
        verbose_name="Информация о продукте",
        related_name="ordered_items",
        blank=True,
        on_delete=models.CASCADE,
    )
    quantity = models.IntegerField()
    state = models.CharField(
        verbose_name="Статус позиции",
        choices=ORDER_ITEM_STATE_CHOICES,
        max_length=15,
        default="basket",
    )
    unit_price = models.IntegerField(default=0)
    price_rrc_snapshot = models.IntegerField(default=0)
    product_name_snapshot = models.CharField(max_length=150, blank=True)
    offer_name_snapshot = models.CharField(max_length=150, blank=True)
    shop_name_snapshot = models.CharField(max_length=150, blank=True)
    external_id_snapshot = models.CharField(max_length=100, blank=True)

    def __str__(self) -> str:
        return f"{self.product_info} x {self.quantity}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="order_item_quantity_gte_1",
            ),
            models.UniqueConstraint(
                fields=["order", "product_info"],
                name="unique_order_item_offer",
            ),
        ]


# 5. Модель импорта прайсов ----
class ImportJob(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        verbose_name="Магазин",
        related_name="import_jobs",
    )
    status = models.CharField(
        verbose_name="Статус импорта",
        choices=IMPORT_JOB_STATUS_CHOICES,
        max_length=15,
        default="pending",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата завершения",
    )
    stats = models.JSONField(
        verbose_name="Статистика",
        blank=True,
        default=dict,
    )
    error_log = models.TextField(
        verbose_name="Лог ошибок",
        blank=True,
        default="",
    )

    def __str__(self) -> str:
        return f"ImportJob #{self.pk} ({self.shop.name}) — {self.status}"

    class Meta:
        verbose_name = "Задача импорта"
        verbose_name_plural = "Задачи импорта"
        ordering = ("-created_at",)
