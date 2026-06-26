from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self) -> None:
        """Подключаем сигналы при старте приложения."""
        import api.signals  # noqa: F401
