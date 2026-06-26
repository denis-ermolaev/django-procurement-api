"""Тесты инвалидации кэша каталога через сигналы."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from api.models import Category, Parameter, Product, ProductInfo, ProductParameter, Shop
from api.services.products import get_active_categories


class CatalogCacheInvalidationMockTests(TestCase):
    """Проверка что сигналы вызывают функцию сброса кэша (mock-тесты)."""

    def setUp(self) -> None:
        self.shop = Shop.objects.create(
            name="Signal test shop", url="https://signal.test", status="active"
        )
        self.category = Category.objects.create(name="Signal category")

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_save_category_invalidates_cache(self) -> None:
        """Сохранение категории сбрасывает кэш."""
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            self.category.name = "Updated category"
            self.category.save()
            mock_invalidate.assert_called_once()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_delete_category_invalidates_cache(self) -> None:
        """Удаление категории сбрасывает кэш."""
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            self.category.delete()
            mock_invalidate.assert_called_once()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_save_product_info_invalidates_cache(self) -> None:
        """Сохранение предложения сбрасывает кэш."""
        product = Product.objects.create(name="Test", category=self.category)
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            ProductInfo.objects.create(
                product=product,
                shop=self.shop,
                name="Test offer",
                quantity=1,
                price=100,
                price_rrc=120,
            )
            mock_invalidate.assert_called_once()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_m2m_category_shops_invalidates_cache(self) -> None:
        """Изменение M2M связи категория-магазин сбрасывает кэш."""
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            self.category.shops.add(self.shop)
            mock_invalidate.assert_called_once()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_save_product_invalidates_cache(self) -> None:
        """Сохранение товара сбрасывает кэш."""
        product = Product.objects.create(name="Test", category=self.category)
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            product.name = "Updated"
            product.save()
            mock_invalidate.assert_called_once()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_delete_product_info_invalidates_cache(self) -> None:
        """Удаление предложения сбрасывает кэш."""
        product = Product.objects.create(name="Test", category=self.category)
        offer = ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Test offer",
            quantity=1,
            price=100,
            price_rrc=120,
        )
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            offer.delete()
            mock_invalidate.assert_called_once()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_save_product_parameter_invalidates_cache(self) -> None:
        """Сохранение характеристики предложения сбрасывает кэш."""
        product = Product.objects.create(name="Test", category=self.category)
        offer = ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Test offer",
            quantity=1,
            price=100,
            price_rrc=120,
        )
        param = Parameter.objects.create(name="color")
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            ProductParameter.objects.create(
                product_info=offer,
                parameter=param,
                value="black",
            )
            mock_invalidate.assert_called_once()

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_delete_product_parameter_invalidates_cache(self) -> None:
        """Удаление характеристики предложения сбрасывает кэш."""
        product = Product.objects.create(name="Test", category=self.category)
        offer = ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Test offer",
            quantity=1,
            price=100,
            price_rrc=120,
        )
        param = Parameter.objects.create(name="color")
        pp = ProductParameter.objects.create(
            product_info=offer,
            parameter=param,
            value="black",
        )
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            pp.delete()
            mock_invalidate.assert_called_once()


class CatalogCacheInvalidationIntegrationTests(TestCase):
    """Интеграционные тесты: проверка что cache.get() возвращает актуальные данные."""

    def setUp(self) -> None:
        self.shop = Shop.objects.create(
            name="Cache test shop", url="https://cache.test", status="active"
        )
        self.category = Category.objects.create(name="Cache category")

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_cache_cleared_on_category_save(self) -> None:
        """После сохранения категории кэш категорий сбрасывается."""
        # Заполняем кэш
        _ = get_active_categories()
        cache_key = "catalog:active_categories"
        self.assertIsNotNone(cache.get(cache_key))

        # Изменяем категорию
        self.category.name = "Updated"
        self.category.save()

        # Кэш должен быть сброшен
        self.assertIsNone(cache.get(cache_key))

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_cache_cleared_on_product_save(self) -> None:
        """После сохранения товара кэш категорий сбрасывается."""
        product = Product.objects.create(name="Test product", category=self.category)

        _ = get_active_categories()
        cache_key = "catalog:active_categories"
        self.assertIsNotNone(cache.get(cache_key))

        product.name = "Updated product"
        product.save()

        self.assertIsNone(cache.get(cache_key))

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_cache_cleared_on_offer_save(self) -> None:
        """После сохранения предложения кэш категорий сбрасывается."""
        product = Product.objects.create(name="Test product", category=self.category)
        ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Test offer",
            quantity=1,
            price=100,
            price_rrc=120,
        )

        _ = get_active_categories()
        cache_key = "catalog:active_categories"
        self.assertIsNotNone(cache.get(cache_key))

        ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Another offer",
            quantity=5,
            price=200,
            price_rrc=250,
        )

        self.assertIsNone(cache.get(cache_key))

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_cache_cleared_on_product_parameter_save(self) -> None:
        """Сохранение характеристики предложения сбрасывает кэш категорий."""
        product = Product.objects.create(name="Test product", category=self.category)
        offer = ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Test offer",
            quantity=1,
            price=100,
            price_rrc=120,
        )
        param = Parameter.objects.create(name="color")

        _ = get_active_categories()
        cache_key = "catalog:active_categories"
        self.assertIsNotNone(cache.get(cache_key))

        ProductParameter.objects.create(
            product_info=offer,
            parameter=param,
            value="black",
        )

        self.assertIsNone(cache.get(cache_key))

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_cache_cleared_on_product_parameter_delete(self) -> None:
        """Удаление характеристики предложения сбрасывает кэш категорий."""
        product = Product.objects.create(name="Test product", category=self.category)
        offer = ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Test offer",
            quantity=1,
            price=100,
            price_rrc=120,
        )
        param = Parameter.objects.create(name="color")
        pp = ProductParameter.objects.create(
            product_info=offer,
            parameter=param,
            value="black",
        )

        _ = get_active_categories()
        cache_key = "catalog:active_categories"
        self.assertIsNotNone(cache.get(cache_key))

        pp.delete()

        self.assertIsNone(cache.get(cache_key))

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_product_info_save_calls_cache_invalidation(self) -> None:
        """Сохранение предложения вызывает invalidate_catalog_cache (проверка через mock)."""
        product = Product.objects.create(name="Test product", category=self.category)
        offer = ProductInfo.objects.create(
            product=product,
            shop=self.shop,
            name="Test offer",
            quantity=10,
            price=100,
            price_rrc=120,
        )
        with patch("api.signals.invalidate_catalog_cache") as mock_invalidate:
            offer.name = "Updated offer"
            offer.save(update_fields=["name"])
            mock_invalidate.assert_called_once()
