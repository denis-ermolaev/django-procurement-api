import os

from .settings import *  # noqa: F403
from .settings import LOGGING, REST_FRAMEWORK  # noqa: F401

# Тестовая БД на отдельном PostgreSQL-контейнере (test-db)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_TEST_NAME", "api_test"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": "test-db",
        "PORT": "5432",
    }
}

ALLOWED_HOSTS = ["testserver"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
LOGGING["handlers"]["console"]["level"] = "CRITICAL"

# Отключаем rate limiting в тестах
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ()
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "shop_register": "1000/minute",
    "shop_import": "1000/minute",
    "order_confirm": "1000/minute",
}

# RQ — синхронный режим (fake), не требует Redis
RQ_FAKE = True
