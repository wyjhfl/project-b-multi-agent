from __future__ import annotations

import hashlib
import json
import time
from threading import Lock
from typing import Any

from app.core.config import settings


class LLMResultCache:
    """LLM 结果缓存（进程内内存版）。"""

    def __init__(self, *, enabled: bool | None = None, ttl_seconds: int | None = None) -> None:
        self._enabled = settings.llm_cache_enabled if enabled is None else bool(enabled)
        self._ttl_seconds = int(settings.llm_cache_ttl_seconds if ttl_seconds is None else ttl_seconds)
        self._lock = Lock()
        self._store: dict[str, tuple[float, Any]] = {}
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Any | None:
        if not self._enabled:
            return None
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self._miss_count += 1
                return None
            expire_at, value = item
            if expire_at > 0 and expire_at < now:
                self._store.pop(key, None)
                self._miss_count += 1
                return None
            self._hit_count += 1
            return value

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        if not self._enabled:
            return
        ttl = self._ttl_seconds if ttl_seconds is None else int(ttl_seconds)
        expire_at = 0.0 if ttl <= 0 else time.time() + ttl
        with self._lock:
            self._store[key] = (expire_at, value)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "ttl_seconds": self._ttl_seconds,
                "size": len(self._store),
                "cache_hit_count": self._hit_count,
                "cache_miss_count": self._miss_count,
            }


def _stable_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_nl2sql_cache_key(
    query: str,
    schema_hash: str,
    prompt_version: str,
    provider: str,
    model: str,
) -> str:
    return "nl2sql:" + _stable_hash(
        {
            "query": query,
            "schema_hash": schema_hash,
            "prompt_version": prompt_version,
            "provider": provider,
            "model": model,
        }
    )


def build_judge_cache_key(
    case_id: str,
    expected: str,
    actual: str,
    rubric: str,
    provider: str,
    model: str,
) -> str:
    return "judge:" + _stable_hash(
        {
            "case_id": case_id,
            "expected": expected,
            "actual": actual,
            "rubric": rubric,
            "provider": provider,
            "model": model,
        }
    )


_GLOBAL_CACHE: LLMResultCache | None = None


def get_llm_result_cache() -> LLMResultCache:
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = LLMResultCache()
    return _GLOBAL_CACHE


def reset_llm_result_cache_for_test() -> None:
    global _GLOBAL_CACHE
    _GLOBAL_CACHE = None
