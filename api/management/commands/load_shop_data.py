import yaml
from django.core.management.base import BaseCommand

from api.models import Category, Parameter, Product, ProductInfo, ProductParameter, Shop


class Command(BaseCommand):
    help = "Load shop YAML data into the database"

    def add_arguments(self, parser):
        parser.add_argument("yaml_file", type=str)

    def handle(self, *_, **options):
        file_path = options["yaml_file"]
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 1. Создаём магазин
        shop_name = data["shop"]
        shop, _ = Shop.objects.get_or_create(name=shop_name)

        # 2. Создаём категории и связываем с магазином
        cat_by_id = {}  # словарь: исходный id -> объект Category
        for cat_data in data["categories"]:
            cat_id = cat_data["id"]
            cat_name = cat_data["name"]
            category, _ = Category.objects.get_or_create(name=cat_name)
            category.shops.add(shop)
            cat_by_id[cat_id] = category

        # 3. Товары и ProductInfo
        for good in data["goods"]:
            # Категория по исходному id
            cat_id = good["category"]
            category = cat_by_id.get(cat_id)
            if not category:
                self.stderr.write(
                    f"Category id {cat_id} not found, skipping {good['name']}"
                )
                continue

            # Product: используем поле model как уникальный идентификатор
            name_code = good["name"]
            product, _ = Product.objects.get_or_create(
                name=name_code, defaults={"category": category}
            )

            # ProductInfo
            product_info = ProductInfo.objects.create(
                product=product,
                shop=shop,
                name=good["name"],
                quantity=good["quantity"],
                price=good["price"],
                price_rrc=good["price_rrc"],
            )

            # Параметры товара
            for param_name, param_value in good.get("parameters", {}).items():
                parameter, _ = Parameter.objects.get_or_create(name=param_name)
                ProductParameter.objects.create(
                    product_info=product_info,
                    parameter=parameter,
                    value=str(param_value),
                )

        self.stdout.write(self.style.SUCCESS("Data loaded successfully"))
