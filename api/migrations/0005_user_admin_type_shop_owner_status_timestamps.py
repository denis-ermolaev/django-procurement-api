# Generated manually for role-based shop moderation.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0004_alter_shop_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="type",
            field=models.CharField(
                choices=[
                    ("shop", "Магазин"),
                    ("buyer", "Покупатель"),
                    ("admin", "Администратор"),
                ],
                default="buyer",
                max_length=5,
                verbose_name="Тип пользователя",
            ),
        ),
        migrations.AlterModelOptions(
            name="shop",
            options={
                "ordering": ("id",),
                "verbose_name": "Магазин",
                "verbose_name_plural": "Магазины",
            },
        ),
        migrations.AddField(
            model_name="shop",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shop",
            name="owner",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="shop",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Владелец",
            ),
        ),
        migrations.AddField(
            model_name="shop",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Ожидает проверки"),
                    ("active", "Активен"),
                    ("blocked", "Заблокирован"),
                    ("archived", "Архивирован"),
                ],
                default="pending",
                max_length=10,
                verbose_name="Статус",
            ),
        ),
        migrations.AddField(
            model_name="shop",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
    ]
