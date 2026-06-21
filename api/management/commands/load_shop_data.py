import logging

import yaml
from django.core.management.base import BaseCommand, CommandError

from api.models import Category, Parameter, Product, ProductInfo, ProductParameter, Shop

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load or update shop YAML data without duplicating existing offers"

    def add_arguments(self, parser):
        parser.add_argument(
            "yaml_file",
            type=str,
            help="Path to YAML file with shop, categories and goods sections.",
        )

    def handle(self, *_, **options):
        # 1. Чтение и базовая проверка YAML ----
        file_path = options["yaml_file"]
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        logger.info("shop_data_load_started file_path=%s", file_path)

        shop_name = data.get("shop")
        if not shop_name:
            logger.error(
                "shop_data_load_failed file_path=%s reason=missing_shop", file_path
            )
            raise CommandError("YAML file must contain the 'shop' field.")

        # 2. Магазин ----
        shop_url = data.get("url", "")
        shop, created = Shop.objects.get_or_create(
            name=shop_name,
            defaults={"url": shop_url},
        )
        logger.info(
            "shop_data_shop_%s shop_id=%s shop_name=%s",
            "created" if created else "selected",
            shop.pk,
            shop.name,
        )
        if not created and shop_url and shop.url != shop_url:
            shop.url = shop_url
            shop.save(update_fields=["url"])
            logger.info("shop_data_shop_url_updated shop_id=%s", shop.pk)

        # 3. Категории ----
        cat_by_id = {}
        for cat_data in data.get("categories", []):
            cat_id = cat_data["id"]
            cat_name = cat_data["name"]
            category, category_created = Category.objects.get_or_create(name=cat_name)
            category.shops.add(shop)
            cat_by_id[cat_id] = category
            logger.debug(
                "shop_data_category_%s source_category_id=%s category_id=%s shop_id=%s",
                "created" if category_created else "selected",
                cat_id,
                category.pk,
                shop.pk,
            )

        # 4. Товары и предложения ----
        loaded_count = 0
        skipped_count = 0
        created_products = 0
        updated_products = 0
        created_offers = 0
        updated_offers = 0
        parameter_count = 0
        for good in data.get("goods", []):
            cat_id = good["category"]
            category = cat_by_id.get(cat_id)
            if not category:
                skipped_count += 1
                logger.warning(
                    (
                        "shop_data_good_skipped_missing_category shop_id=%s "
                        "source_category_id=%s good_name=%s"
                    ),
                    shop.pk,
                    cat_id,
                    good["name"],
                )
                self.stderr.write(
                    f"Category id {cat_id} not found, skipping {good['name']}"
                )
                continue

            product, product_created = Product.objects.update_or_create(
                name=good["name"], defaults={"category": category}
            )
            if product_created:
                created_products += 1
            else:
                updated_products += 1

            # 4.1. ProductInfo уникален в рамках товара, магазина и имени из прайса.
            # Повторная загрузка обновляет остаток и цены вместо создания дубля.
            product_info, offer_created = ProductInfo.objects.update_or_create(
                product=product,
                shop=shop,
                name=good["name"],
                defaults={
                    "quantity": good["quantity"],
                    "price": good["price"],
                    "price_rrc": good["price_rrc"],
                },
            )
            if offer_created:
                created_offers += 1
            else:
                updated_offers += 1
            logger.debug(
                (
                    "shop_data_offer_%s shop_id=%s product_id=%s product_info_id=%s "
                    "quantity=%s price=%s"
                ),
                "created" if offer_created else "updated",
                shop.pk,
                product.pk,
                product_info.pk,
                product_info.quantity,
                product_info.price,
            )

            # 4.2. Характеристики предложения заменяются целиком, чтобы удаленные из
            # YAML параметры не оставались в БД после повторной загрузки.
            ProductParameter.objects.filter(product_info=product_info).delete()
            for param_name, param_value in good.get("parameters", {}).items():
                parameter, _ = Parameter.objects.get_or_create(name=param_name)
                ProductParameter.objects.create(
                    product_info=product_info,
                    parameter=parameter,
                    value=str(param_value),
                )
                parameter_count += 1
            loaded_count += 1

        logger.info(
            (
                "shop_data_load_completed shop_id=%s loaded_count=%s "
                "skipped_count=%s created_products=%s updated_products=%s "
                "created_offers=%s updated_offers=%s parameter_count=%s"
            ),
            shop.pk,
            loaded_count,
            skipped_count,
            created_products,
            updated_products,
            created_offers,
            updated_offers,
            parameter_count,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Data loaded successfully: {loaded_count} goods")
        )
