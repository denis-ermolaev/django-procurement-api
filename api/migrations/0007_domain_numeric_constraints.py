# Generated manually from domain invariants.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0006_catalog_offer_order_item_statuses"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gte", 0)),
                name="product_info_quantity_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.CheckConstraint(
                condition=models.Q(("reserved_quantity__gte", 0)),
                name="product_info_reserved_quantity_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.CheckConstraint(
                condition=models.Q(("reserved_quantity__lte", models.F("quantity"))),
                name="product_info_reserved_lte_quantity",
            ),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.CheckConstraint(
                condition=models.Q(("price__gt", 0)),
                name="product_info_price_gt_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.CheckConstraint(
                condition=models.Q(("price_rrc__gte", 0)),
                name="product_info_price_rrc_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gte", 1)),
                name="order_item_quantity_gte_1",
            ),
        ),
    ]
