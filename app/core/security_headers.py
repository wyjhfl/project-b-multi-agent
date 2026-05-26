from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import Settings


def parse_csv_config(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool = True):
        super().__init__(app)
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not self._enabled:
            return response
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "0"
        return response


def build_cors_options(current_settings: Settings) -> dict:
    origins = parse_csv_config(current_settings.cors_allow_origins)
    methods = parse_csv_config(current_settings.cors_allow_methods)
    headers = parse_csv_config(current_settings.cors_allow_headers)

    return {
        "allow_origins": origins,
        "allow_credentials": bool(current_settings.cors_allow_credentials),
        "allow_methods": methods or ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": headers or ["Authorization", "Content-Type"],
    }
