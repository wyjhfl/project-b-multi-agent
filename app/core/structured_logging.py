from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core.config import settings

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "key",
    "password",
    "secret",
    "jwt",
    "database_url",
    "redis_url",
}

_DSN_SCHEME_PATTERN = re.compile(r"^(postgresql(?:\+psycopg)?|redis)$", re.IGNORECASE)
_JSON_LOGGER_NAME = "app.structured"
SENSITIVE_KEY_PATTERNS = (
    "token",
    "key",
    "api_key",
    "apikey",
    "secret",
    "password",
    "authorization",
    "cookie",
    "jwt",
    "database_url",
    "redis_url",
)


def setup_structured_logger() -> logging.Logger:
    logger = logging.getLogger(_JSON_LOGGER_NAME)
    log_level_name = (settings.log_level or "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


def _mask_plain_text(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return "***"
    if len(cleaned) <= 4:
        return "***"
    return f"{cleaned[:2]}***{cleaned[-2:]}"


def _redact_dsn(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except Exception:
        return _mask_plain_text(value)

    if not _DSN_SCHEME_PATTERN.match(parsed.scheme or ""):
        return _mask_plain_text(value)

    if parsed.username is None and parsed.password is None:
        return urlunsplit(parsed)
    safe_user = parsed.username or "user"
    safe_userinfo = f"{safe_user}:***"

    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    safe_netloc = f"{safe_userinfo}@{host}{port}"
    return urlunsplit((parsed.scheme, safe_netloc, parsed.path, parsed.query, parsed.fragment))


def redact_sensitive_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return "***"
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]

    text = str(value)
    if "://" in text:
        return _redact_dsn(text)
    return _mask_plain_text(text)


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = str(key).lower()
        matched_sensitive = key_lower in SENSITIVE_KEYS or any(
            pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS
        )
        if matched_sensitive:
            redacted[key] = redact_sensitive_value(value)
            continue
        if isinstance(value, dict):
            redacted[key] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_mapping(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def build_log_event(
    *,
    event_type: str,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    actor: str = "anonymous",
    client_ip: str | None = None,
    user_agent: str | None = None,
    error_type: str | None = None,
    result: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "latency_ms": round(float(latency_ms), 2),
        "actor": actor or "anonymous",
    }
    if settings.log_include_client_ip:
        event["client_ip"] = client_ip or "unknown"
    if settings.log_include_user_agent:
        event["user_agent"] = user_agent or ""
    if error_type:
        event["error_type"] = error_type
    if result:
        event["result"] = result

    if extras:
        merged = dict(extras)
        if settings.log_redaction_enabled:
            merged = redact_mapping(merged)
        event.update(merged)

    return event


def emit_log_event(event: dict[str, Any]) -> None:
    logger = setup_structured_logger()
    logger.log(logger.level or logging.INFO, json.dumps(event, ensure_ascii=False))
