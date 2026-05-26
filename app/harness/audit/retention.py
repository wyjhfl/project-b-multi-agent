from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings
from app.core.structured_logging import redact_mapping

AUDIT_EXPORT_FIELD_WHITELIST = (
    "event_id",
    "event_type",
    "task_id",
    "actor",
    "action",
    "severity",
    "outcome",
    "created_at",
    "request_id",
    "summary",
    "detail_redacted",
)

_PROMPT_KEYS = ("prompt", "query", "user_query", "input_text", "raw_prompt", "sql_prompt")


def validate_audit_retention_settings(current_settings: Settings) -> list[str]:
    errors: list[str] = []
    if current_settings.audit_retention_enabled and int(current_settings.audit_retention_days or 0) <= 0:
        errors.append("AUDIT_RETENTION_DAYS 必须大于 0。")
    if int(current_settings.audit_export_max_rows or 0) <= 0 or int(current_settings.audit_export_max_rows or 0) > 10000:
        errors.append("AUDIT_EXPORT_MAX_ROWS 必须在 1 到 10000 范围内。")
    if (current_settings.audit_export_format or "").strip().lower() not in {"jsonl"}:
        errors.append("AUDIT_EXPORT_FORMAT 当前仅支持 jsonl。")
    if current_settings.audit_export_enabled and not bool(current_settings.audit_export_redaction_enabled):
        errors.append("AUDIT_EXPORT_ENABLED=true 时必须启用 AUDIT_EXPORT_REDACTION_ENABLED。")
    return errors


def get_audit_retention_cutoff(now: datetime, retention_days: int) -> datetime:
    base = now
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base - timedelta(days=max(1, int(retention_days)))


def _sanitize_prompt_like_fields(data: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        lower_key = str(key).lower()
        if any(marker in lower_key for marker in _PROMPT_KEYS):
            sanitized[key] = "[REDACTED_PROMPT]"
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_prompt_like_fields(value)
        elif isinstance(value, list):
            nested: list[Any] = []
            for item in value:
                if isinstance(item, dict):
                    nested.append(_sanitize_prompt_like_fields(item))
                else:
                    nested.append(item)
            sanitized[key] = nested
        else:
            sanitized[key] = value
    return sanitized


def sanitize_audit_event_for_export(event: dict[str, Any], *, redaction_enabled: bool = True) -> dict[str, Any]:
    detail_raw = event.get("detail")
    if isinstance(detail_raw, dict):
        detail = _sanitize_prompt_like_fields(detail_raw)
    else:
        detail = {}

    if redaction_enabled:
        detail = redact_mapping(detail)

    summary = str(event.get("reason") or event.get("action") or event.get("event_type") or "")
    summary = summary.strip()
    if len(summary) > 200:
        summary = f"{summary[:197]}..."

    sanitized = {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "task_id": event.get("task_id"),
        "actor": event.get("actor") or "system",
        "action": event.get("action") or "",
        "severity": event.get("severity"),
        "outcome": event.get("outcome"),
        "created_at": event.get("timestamp"),
        "request_id": detail.get("request_id") if isinstance(detail, dict) else None,
        "summary": summary,
        "detail_redacted": detail,
    }
    return {key: sanitized.get(key) for key in AUDIT_EXPORT_FIELD_WHITELIST}
