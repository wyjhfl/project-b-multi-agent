from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client = None


class NoopRedisClient:
    def get(self, key: str) -> None:
        return None

    def set(self, key: str, value: Any, ex: int | None = None) -> None:
        pass

    def delete(self, key: str) -> None:
        pass

    def exists(self, key: str) -> bool:
        return False

    def incr(self, key: str) -> int:
        return 0

    def expire(self, key: str, seconds: int) -> None:
        pass

    def ping(self) -> bool:
        return False

    def close(self) -> None:
        pass


def get_redis_client() -> NoopRedisClient | Any:
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not settings.redis_enabled:
        _redis_client = NoopRedisClient()
        return _redis_client

    try:
        import redis as redis_lib
        _redis_client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Redis connected: %s", settings.redis_url)
    except Exception as exc:
        logger.warning("Redis connection failed: %s, falling back to NoopRedisClient", exc)
        _redis_client = NoopRedisClient()

    return _redis_client


def check_redis_health() -> dict[str, str]:
    if not settings.redis_enabled:
        return {"status": "disabled", "backend": "noop"}
    try:
        client = get_redis_client()
        if isinstance(client, NoopRedisClient):
            return {"status": "disabled", "backend": "noop"}
        client.ping()
        return {"status": "ok", "backend": "redis"}
    except Exception as e:
        return {"status": "error", "backend": "redis", "error": str(e)}
