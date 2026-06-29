"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
#                  WSGI MIDDLEWARE: Reverse Proxy Script Name                  #
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #

# Множество «локальных» хостов, которые НЕ считаются reverse-proxy.
# Если HTTP_HOST содержит любой из этих префиксов — запрос считается прямым.
_LOCAL_HOST_PREFIXES = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "web", "::1"})


class ReverseProxyPrefix:
    """WSGI middleware — динамический SCRIPT_NAME для code-server / reverse proxy.

    code-server проксирует https://host:8080/proxy/8000/ → http://web:8000/.
    Он передаёт полный путь (включая /proxy/8000/) в PATH_INFO Django без
    вычитания префикса.  Если просто установить SCRIPT_NAME без коррекции
    PATH_INFO, то:
      - SCRIPT_NAME  = /proxy/8000
      - PATH_INFO    = /proxy/8000/api/docs/  (code-server не вырезает)
      → Django получает полный виртуальный путь SCRIPT_NAME + PATH_INFO =
        /proxy/8000/proxy/8000/api/docs/ — задвоение.
      → URL-роутинг смотрит на PATH_INFO = /proxy/8000/api/docs/ — 404.

    Решение:
        1. Установить SCRIPT_NAME = /proxy/8000 (чтобы reverse(), пагинация,
           build_absolute_uri() генерировали URL с префиксом).
        2. Вычесть /proxy/8000 из PATH_INFO (чтобы URL-роутинг Django видел
           только /api/docs/, /api/schema/ и т.д.).

    Прямые запросы (localhost:8000, HTTP_HOST — локальный) не получают
    префикса — оба режима работают одновременно.

    Детекция прокси (по приоритету):
        1. X-Forwarded-For / X-Forwarded-Host / X-Forwarded-Proto.
        2. HTTP_HOST не содержит локального префикса — fallback для прокси,
           которые не добавляют X-Forwarded-* (code-server без nginx).
    """

    def __init__(self, application):
        self.application = application
        self._proxy_script_name = os.environ.get("DJANGO_PROXY_SCRIPT_NAME", "")

    def __call__(self, environ, start_response):
        if self._proxy_script_name and self._detect_proxy(environ):
            environ["SCRIPT_NAME"] = self._proxy_script_name

            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
            #  Устанавливаем X-Forwarded-Proto для SECURE_PROXY_SSL_HEADER #
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
            # code-server принимает HTTPS, но проксирует на HTTP без
            # установки X-Forwarded-*.  Без него Django считает протокол
            # запроса HTTP и генерирует URL схемы OpenAPI с http://, что
            # приводит к mixed-content при вызове API из Swagger UI.
            environ.setdefault("HTTP_X_FORWARDED_PROTO", "https")

            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
            #  Вычитаем префикс из PATH_INFO                               #
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
            path_info = environ.get("PATH_INFO", "")
            if path_info.startswith(self._proxy_script_name):
                environ["PATH_INFO"] = path_info.removeprefix(self._proxy_script_name)

                # Если после вычитания осталась пустая строка — нормализуем
                # до '/', чтобы Django не споткнулся о пустой PATH_INFO.
                if not environ["PATH_INFO"]:
                    environ["PATH_INFO"] = "/"

        return self.application(environ, start_response)

    @staticmethod
    def _detect_proxy(environ: dict) -> bool:
        """Определяет, пришёл ли запрос через reverse-proxy."""
        # 1. Стандартные заголовки reverse-proxy
        if (
            environ.get("HTTP_X_FORWARDED_FOR")
            or environ.get("HTTP_X_FORWARDED_HOST")
            or environ.get("HTTP_X_FORWARDED_PROTO")
        ):
            return True

        # 2. Fallback: проверка Host (code-server может не слать X-Forwarded-*)
        host = environ.get("HTTP_HOST", "")
        if host:
            hostname = host.split(":")[0]  # отсекаем порт
            if hostname not in _LOCAL_HOST_PREFIXES:
                return True

        return False


# ---------------------------------------------------------------------------- #

application = ReverseProxyPrefix(get_wsgi_application())
