from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Protocol

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.security_headers import parse_csv_config


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if not settings.request_size_limit_enabled:
            return await call_next(request)
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        limit = max(1, int(settings.request_size_limit_bytes))
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = -1
            if size > limit:
                return JSONResponse(
                    status_code=413,
                    content={"error": "request_too_large", "limit_bytes": limit},
                )
        return await call_next(request)


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, max_requests: int, burst: int, window_seconds: int = 60) -> tuple[bool, int]:
        now = time.time()
        min_allowed = now - window_seconds
        capacity = max(1, max_requests + max(0, burst))
        with self._lock:
            hits = [ts for ts in self._requests.get(key, []) if ts >= min_allowed]
            if len(hits) >= capacity:
                retry_after = max(1, int(window_seconds - (now - hits[0])))
                self._requests[key] = hits
                return False, retry_after
            hits.append(now)
            self._requests[key] = hits
            return True, 0


class RateLimiterBackend(Protocol):
    def allow(self, key: str, max_requests: int, burst: int, window_seconds: int = 60) -> tuple[bool, int]:
        ...


class RedisRateLimiter:
    def __init__(self, fallback: InMemoryRateLimiter | None = None) -> None:
        self._fallback = fallback or InMemoryRateLimiter()

    def allow(self, key: str, max_requests: int, burst: int, window_seconds: int = 60) -> tuple[bool, int]:
        from app.cache.redis_client import NoopRedisClient, get_redis_client

        client = get_redis_client()
        if isinstance(client, NoopRedisClient):
            return self._fallback.allow(key, max_requests, burst, window_seconds)

        now = time.time()
        capacity = max(1, max_requests + max(0, burst))
        bucket = int(now // window_seconds)
        redis_key = f"rate_limit:{bucket}:{key}"
        try:
            count = int(client.incr(redis_key))
            if count == 1:
                client.expire(redis_key, window_seconds)
            if count > capacity:
                retry_after = max(1, int(window_seconds - (now % window_seconds)))
                return False, retry_after
            return True, 0
        except Exception:
            return self._fallback.allow(key, max_requests, burst, window_seconds)


_RATE_LIMITER = InMemoryRateLimiter()
_REDIS_RATE_LIMITER = RedisRateLimiter(fallback=_RATE_LIMITER)


def _get_rate_limiter() -> RateLimiterBackend:
    if (settings.rate_limit_backend or "memory").strip().lower() == "redis":
        return _REDIS_RATE_LIMITER
    return _RATE_LIMITER


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        exempt_paths = set(parse_csv_config(settings.rate_limit_exempt_paths))
        if request.url.path in exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        allowed, retry_after = _get_rate_limiter().allow(
            key=key,
            max_requests=max(1, int(settings.rate_limit_requests_per_minute)),
            burst=max(0, int(settings.rate_limit_burst)),
            window_seconds=60,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


class BasicAbuseGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if not settings.abuse_guard_enabled:
            return await call_next(request)
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        if len(str(request.url.path)) > 2048:
            return JSONResponse(
                status_code=414,
                content={"error": "request_rejected", "reason": "path_too_long"},
            )

        header_items = list(request.headers.items())
        if len(header_items) > 120:
            return JSONResponse(
                status_code=400,
                content={"error": "request_rejected", "reason": "too_many_headers"},
            )

        for _, value in header_items:
            if len(value) > 8192:
                return JSONResponse(
                    status_code=400,
                    content={"error": "request_rejected", "reason": "header_value_too_large"},
                )

        return await call_next(request)
