from __future__ import annotations

from fastapi.testclient import TestClient

import app.core.request_guards as guard_mod
from app.core.config import settings
from app.main import app

client = TestClient(app)


def _reset_rate_limiter_state():
    guard_mod._RATE_LIMITER._requests.clear()


def test_health_exempt_from_rate_limit(monkeypatch):
    _reset_rate_limiter_state()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_burst", 0)
    monkeypatch.setattr(settings, "rate_limit_exempt_paths", "/health")
    first = client.get("/health")
    second = client.get("/health")
    assert first.status_code == 200
    assert second.status_code == 200


def test_preview_request_too_large_returns_413(monkeypatch):
    monkeypatch.setattr(settings, "request_size_limit_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_bytes", 64)
    payload = '{"query":"' + ("a" * 512) + '"}'
    response = client.post(
        "/nl2sql/preview",
        content=payload,
        headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
    )
    assert response.status_code == 413
    assert response.json()["error"] == "request_too_large"


def test_normal_request_not_blocked_by_size_limit(monkeypatch):
    _reset_rate_limiter_state()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "request_size_limit_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_bytes", 1024 * 1024)
    response = client.post("/nl2sql/preview", json={"query": "今天GMV多少"})
    assert response.status_code == 200


def test_rate_limit_blocks_non_exempt_endpoint(monkeypatch):
    _reset_rate_limiter_state()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_requests_per_minute", 1)
    monkeypatch.setattr(settings, "rate_limit_burst", 0)
    monkeypatch.setattr(settings, "rate_limit_exempt_paths", "/health")
    first = client.get("/deployment/check")
    second = client.get("/deployment/check")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"] == "rate_limited"


def test_options_preflight_not_blocked(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "request_size_limit_enabled", True)
    monkeypatch.setattr(settings, "abuse_guard_enabled", True)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200


def test_abuse_guard_rejects_too_many_headers(monkeypatch):
    monkeypatch.setattr(settings, "abuse_guard_enabled", True)
    headers = {f"x-test-{i}": "v" for i in range(130)}
    response = client.get("/health", headers=headers)
    assert response.status_code == 400
    assert response.json()["error"] == "request_rejected"
