import yaml
from django.core.management.base import BaseCommand, CommandError

from api.models import Category, Parameter, Product, ProductInfo, ProductParameter, Shop


class Command(BaseCommand):
    help = "Load shop YAML data into the database"

    def add_arguments(self, parser):
        parser.add_argument("yaml_file", type=str)

    def handle(self, *_, **options):
        # 1. Чтение и базовая проверка YAML ----
        file_path = options["yaml_file"]
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        shop_name = data.get("shop")
        if not shop_name:
            raise CommandError("YAML file must contain the 'shop' field.")

        # 2. Магазин ----
        shop_url = data.get("url", "")
        shop, created = Shop.objects.get_or_create(
            name=shop_name,
            defaults={"url": shop_url},
        )
        if not created and shop_url and shop.url != shop_url:
            shop.url = shop_url
            shop.save(update_fields=["url"])

        # 3. Категории ----
        cat_by_id = {}
        for cat_data in data.get("categories", []):
            cat_id = cat_data["id"]
            cat_name = cat_data["name"]
            category, _ = Category.objects.get_or_create(name=cat_name)
            category.shops.add(shop)
            cat_by_id[cat_id] = category

        # 4. Товары и предложения ----
        loaded_count = 0
        for good in data.get("goods", []):
            cat_id = good["category"]
            category = cat_by_id.get(cat_id)
            if not category:
                self.stderr.write(
                    f"Category id {cat_id} not found, skipping {good['name']}"
                )
                continue

            product, _ = Product.objects.update_or_create(
                name=good["name"], defaults={"category": category}
            )

            product_info, _ = ProductInfo.objects.update_or_create(
                product=product,
                shop=shop,
                name=good["name"],
                defaults={
                    "quantity": good["quantity"],
                    "price": good["price"],
                    "price_rrc": good["price_rrc"],
                },
            )

            ProductParameter.objects.filter(product_info=product_info).delete()
            for param_name, param_value in good.get("parameters", {}).items():
                parameter, _ = Parameter.objects.get_or_create(name=param_name)
                ProductParameter.objects.create(
                    product_info=product_info,
                    parameter=parameter,
                    value=str(param_value),
                )
            loaded_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Data loaded successfully: {loaded_count} goods")
        )
