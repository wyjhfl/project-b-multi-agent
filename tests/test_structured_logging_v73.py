from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.structured_logging import build_log_event, redact_mapping
from app.main import app

client = TestClient(app)


def test_redact_mapping_masks_sensitive_fields():
    payload = {
        "authorization": "Bearer SECRET-TOKEN-123",
        "cookie": "session=abc",
        "token": "token-value",
        "api_key": "sk-test-secret",
        "password": "pass-12345",
        "secret": "very-secret",
        "database_url": "postgresql+psycopg://agent:db-password@db:5432/project_b",
        "redis_url": "redis://:redis-password@redis:6379/0",
        "normal": "ok",
    }

    redacted = redact_mapping(payload)
    serialized = json.dumps(redacted, ensure_ascii=False)
    assert redacted["normal"] == "ok"
    assert "SECRET-TOKEN-123" not in serialized
    assert "session=abc" not in serialized
    assert "db-password" not in serialized
    assert "redis-password" not in serialized


def test_build_log_event_uses_expected_fields():
    event = build_log_event(
        event_type="http_request",
        request_id="req-001",
        method="GET",
        path="/health",
        status_code=200,
        latency_ms=12.34,
        actor="anonymous",
        client_ip="127.0.0.1",
        user_agent="pytest",
        result="ok",
    )
    assert event["event_type"] == "http_request"
    assert event["request_id"] == "req-001"
    assert event["path"] == "/health"
    assert "timestamp" in event


def test_health_returns_request_id_header(monkeypatch):
    monkeypatch.setattr(settings, "structured_logging_enabled", True)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_request_id_passthrough(monkeypatch):
    monkeypatch.setattr(settings, "structured_logging_enabled", True)
    response = client.get("/health", headers={"X-Request-ID": "custom-req-id"})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "custom-req-id"


def test_rate_limit_response_keeps_request_id(monkeypatch):
    import app.core.request_guards as guard_mod

    guard_mod._RATE_LIMITER._requests.clear()
    monkeypatch.setattr(settings, "structured_logging_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_burst", 0)
    monkeypatch.setattr(settings, "rate_limit_exempt_paths", "/health")
    first = client.get("/deployment/check")
    second = client.get("/deployment/check")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("X-Request-ID")


def test_request_too_large_keeps_request_id(monkeypatch):
    monkeypatch.setattr(settings, "structured_logging_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_bytes", 64)
    payload = '{"query":"' + ("a" * 512) + '"}'
    response = client.post(
        "/nl2sql/preview",
        content=payload,
        headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
    )
    assert response.status_code == 413
    assert response.headers.get("X-Request-ID")


def test_logs_are_json_and_no_sensitive_plain_text(monkeypatch):
    import app.core.request_logging as request_logging_mod

    captured_events: list[dict] = []

    def _capture_event(event: dict) -> None:
        captured_events.append(event)

    monkeypatch.setattr(settings, "structured_logging_enabled", True)
    monkeypatch.setattr(settings, "log_redaction_enabled", True)
    monkeypatch.setattr(request_logging_mod, "emit_log_event", _capture_event)

    response = client.get(
        "/health",
        headers={
            "Authorization": "Bearer SECRET-ABC-123",
            "Cookie": "session=secret-cookie",
            "X-Request-ID": "log-check-001",
        },
    )

    assert response.status_code == 200
    assert captured_events
    payload = json.dumps(captured_events, ensure_ascii=False)
    assert "SECRET-ABC-123" not in payload
    assert "secret-cookie" not in payload
    assert any(item.get("request_id") == "log-check-001" for item in captured_events)
