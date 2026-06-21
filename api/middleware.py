import logging
from collections.abc import Callable
from time import monotonic

from django.http import HttpRequest, HttpResponseBase

# 1. HTTP request logging ----
REQUEST_LOGGER = logging.getLogger("api.request")


class RequestLogMiddleware:
    """Логирует итог обработки HTTP-запроса без тела запроса и ответа."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        started_at = monotonic()

        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = self.get_duration_ms(started_at)
            REQUEST_LOGGER.exception(
                ("request_failed method=%s path=%s duration_ms=%s user_id=%s"),
                request.method,
                request.path,
                duration_ms,
                self.get_user_id(request),
                extra={
                    "method": request.method,
                    "path": request.path,
                    "duration_ms": duration_ms,
                    "user_id": self.get_user_id(request),
                },
            )
            raise

        duration_ms = self.get_duration_ms(started_at)
        status_code = response.status_code
        REQUEST_LOGGER.log(
            self.get_response_log_level(status_code),
            "request_completed method=%s path=%s status_code=%s duration_ms=%s user_id=%s",
            request.method,
            request.path,
            status_code,
            duration_ms,
            self.get_user_id(request),
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "user_id": self.get_user_id(request),
            },
        )
        return response

    @staticmethod
    def get_duration_ms(started_at: float) -> int:
        return int((monotonic() - started_at) * 1000)

    @staticmethod
    def get_response_log_level(status_code: int) -> int:
        if status_code >= 500:
            return logging.ERROR
        if status_code >= 400:
            return logging.WARNING
        return logging.INFO

    @staticmethod
    def get_user_id(request: HttpRequest) -> int | None:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return user.pk
