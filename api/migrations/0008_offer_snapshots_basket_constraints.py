# Generated manually from AGENTS_SPEC.md domain invariants.

import django.utils.timezone
from django.db import migrations, models
from django.db.models import Count


def merge_duplicate_parameters(apps, schema_editor):
    parameter_model = apps.get_model("api", "Parameter")
    product_parameter_model = apps.get_model("api", "ProductParameter")

    duplicated_names = (
        parameter_model.objects.values("name")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for duplicated in duplicated_names:
        parameters = list(
            parameter_model.objects.filter(name=duplicated["name"]).order_by("id")
        )
        keep_parameter = parameters[0]
        for parameter in parameters[1:]:
            product_parameters = product_parameter_model.objects.filter(
                parameter=parameter
            )
            for product_parameter in product_parameters:
                existing = product_parameter_model.objects.filter(
                    product_info_id=product_parameter.product_info_id,
                    parameter=keep_parameter,
                ).first()
                if existing:
                    product_parameter.delete()
                else:
                    product_parameter.parameter = keep_parameter
                    product_parameter.save(update_fields=["parameter"])
            parameter.delete()


def merge_duplicate_baskets(apps, schema_editor):
    order_model = apps.get_model("api", "Order")
    order_item_model = apps.get_model("api", "OrderItem")

    duplicated_users = (
        order_model.objects.filter(state="basket")
        .values("user_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for duplicated in duplicated_users:
        baskets = list(
            order_model.objects.filter(
                user_id=duplicated["user_id"],
                state="basket",
            ).order_by("id")
        )
        keep_basket = baskets[0]
        for stale_basket in baskets[1:]:
            for stale_item in order_item_model.objects.filter(order=stale_basket):
                existing_item = order_item_model.objects.filter(
                    order=keep_basket,
                    product_info_id=stale_item.product_info_id,
                ).first()
                if existing_item:
                    existing_item.quantity += stale_item.quantity
                    existing_item.save(update_fields=["quantity"])
                    stale_item.delete()
                else:
                    stale_item.order = keep_basket
                    stale_item.save(update_fields=["order"])
            stale_basket.delete()


def merge_duplicate_order_items(apps, schema_editor):
    order_item_model = apps.get_model("api", "OrderItem")

    duplicated_items = (
        order_item_model.objects.values("order_id", "product_info_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for duplicated in duplicated_items:
        items = list(
            order_item_model.objects.filter(
                order_id=duplicated["order_id"],
                product_info_id=duplicated["product_info_id"],
            ).order_by("id")
        )
        keep_item = items[0]
        for stale_item in items[1:]:
            keep_item.quantity += stale_item.quantity
            stale_item.delete()
        keep_item.save(update_fields=["quantity"])


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0007_domain_numeric_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="shop",
            name="is_accepting_orders",
            field=models.BooleanField(default=True, verbose_name="Принимает заказы"),
        ),
        migrations.AddField(
            model_name="productinfo",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AddField(
            model_name="productinfo",
            name="model",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="productinfo",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="orderitem",
            name="unit_price",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="price_rrc_snapshot",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_name_snapshot",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="offer_name_snapshot",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="shop_name_snapshot",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="external_id_snapshot",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(merge_duplicate_parameters, migrations.RunPython.noop),
        migrations.RunPython(merge_duplicate_baskets, migrations.RunPython.noop),
        migrations.RunPython(merge_duplicate_order_items, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="parameter",
            name="name",
            field=models.CharField(max_length=150, unique=True),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.UniqueConstraint(
                condition=models.Q(("external_id", ""), _negated=True),
                fields=("shop", "external_id"),
                name="unique_offer_shop_external_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="productparameter",
            constraint=models.UniqueConstraint(
                fields=("product_info", "parameter"),
                name="unique_product_parameter_per_offer",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                condition=models.Q(("state", "basket")),
                fields=("user",),
                name="unique_active_basket_per_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.UniqueConstraint(
                fields=("order", "product_info"),
                name="unique_order_item_offer",
            ),
        ),
    ]
