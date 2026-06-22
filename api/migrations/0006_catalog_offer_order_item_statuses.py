# Generated manually for DOMAIN.md order and catalog invariants.

from django.db import migrations, models


def mark_existing_order_items(apps, schema_editor):
    order_item = apps.get_model("api", "OrderItem")
    order_item.objects.exclude(order__state="basket").update(state="confirmed")


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0005_user_admin_type_shop_owner_status_timestamps"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="state",
            field=models.CharField(
                choices=[
                    ("basket", "Статус корзины"),
                    ("confirmed", "Подтвержден"),
                    ("processing", "В обработке"),
                    ("sent", "Отправлен"),
                    ("delivered", "Доставлен"),
                    ("partially_canceled", "Частично отменен"),
                    ("canceled", "Отменен"),
                ],
                max_length=20,
                verbose_name="Статус",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="status",
            field=models.CharField(
                choices=[("active", "Активен"), ("archived", "Архивирован")],
                default="active",
                max_length=10,
                verbose_name="Статус",
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="cancellation_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="state",
            field=models.CharField(
                choices=[
                    ("basket", "В корзине"),
                    ("confirmed", "Подтверждена"),
                    ("accepted", "Принята магазином"),
                    ("assembled", "Собрана"),
                    ("sent", "Отправлена"),
                    ("delivered", "Доставлена"),
                    ("canceled", "Отменена"),
                ],
                default="basket",
                max_length=15,
                verbose_name="Статус позиции",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="status",
            field=models.CharField(
                choices=[("active", "Активен"), ("archived", "Архивирован")],
                default="active",
                max_length=10,
                verbose_name="Статус",
            ),
        ),
        migrations.AddField(
            model_name="productinfo",
            name="reserved_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="productinfo",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Активно"),
                    ("hidden", "Скрыто"),
                    ("archived", "Архивировано"),
                    ("blocked", "Заблокировано"),
                ],
                default="active",
                max_length=10,
                verbose_name="Статус",
            ),
        ),
        migrations.RunPython(mark_existing_order_items, migrations.RunPython.noop),
    ]
