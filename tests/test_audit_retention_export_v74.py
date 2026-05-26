from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.auth.models import User, UserRole
from app.core.config import settings
from app.harness.audit.retention import (
    AUDIT_EXPORT_FIELD_WHITELIST,
    get_audit_retention_cutoff,
    sanitize_audit_event_for_export,
)
from app.main import app, get_audit_store, reset_runtime_for_test
from app.models.schemas import AuditEvent

client = TestClient(app)


def _token(username: str, role: str) -> str:
    user = User(
        user_id=f"usr_{username}",
        username=username,
        password_hash="x",
        roles=[UserRole(role)],
    )
    return create_access_token(user)


def test_retention_cutoff_calculation():
    now = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    cutoff = get_audit_retention_cutoff(now, 90)
    assert cutoff == now - timedelta(days=90)


def test_sanitize_export_keeps_whitelist_and_masks_sensitive():
    event = {
        "event_id": "aud_001",
        "event_type": "tool_call",
        "timestamp": "2026-05-26T00:00:00+00:00",
        "task_id": "task_1",
        "actor": "operator",
        "action": "call_tool",
        "outcome": "success",
        "severity": "info",
        "reason": "test reason",
        "detail": {
            "request_id": "req-001",
            "token": "secret-token",
            "api_key": "sk-test",
            "password": "pwd-001",
            "secret": "secret-001",
            "database_url": "postgresql+psycopg://agent:db-pass@db:5432/project_b",
            "redis_url": "redis://:redis-pass@redis:6379/0",
            "prompt": "原始 prompt 不能导出",
        },
    }
    exported = sanitize_audit_event_for_export(event, redaction_enabled=True)
    assert set(exported.keys()) == set(AUDIT_EXPORT_FIELD_WHITELIST)
    payload = json.dumps(exported, ensure_ascii=False)
    assert "secret-token" not in payload
    assert "sk-test" not in payload
    assert "pwd-001" not in payload
    assert "secret-001" not in payload
    assert "db-pass" not in payload
    assert "redis-pass" not in payload
    assert "原始 prompt 不能导出" not in payload
    assert "[REDACTED_PROMPT]" in payload


def test_export_never_leaks_sensitive_detail_fields(monkeypatch):
    reset_runtime_for_test()
    monkeypatch.setattr(settings, "audit_export_enabled", True)
    monkeypatch.setattr(settings, "audit_export_redaction_enabled", True)
    monkeypatch.setattr(settings, "audit_export_max_rows", 10)

    store = get_audit_store()
    store.append(
        AuditEvent(
            event_type="export_sensitive_test",
            actor="tester",
            action="export_sensitive_action",
            detail={
                "token": "token-plain",
                "api_key": "api-key-plain",
                "authorization": "Bearer auth-plain",
                "cookie": "session=cookie-plain",
                "password": "pwd-plain",
                "secret": "secret-plain",
                "database_url": "postgresql+psycopg://agent:db-password@db:5432/project_b",
                "redis_url": "redis://:redis-password@redis:6379/0",
                "prompt": "原始 prompt 文本",
                "query": "原始 query 文本",
                "user_query": "原始 user_query 文本",
                "raw_prompt": "原始 raw_prompt 文本",
                "sql_prompt": "原始 sql_prompt 文本",
            },
        )
    )

    resp = client.get("/audit/events/export", params={"event_type": "export_sensitive_test"})
    assert resp.status_code == 200
    text = resp.text
    for raw in (
        "token-plain",
        "api-key-plain",
        "auth-plain",
        "cookie-plain",
        "pwd-plain",
        "secret-plain",
        "db-password",
        "redis-password",
        "原始 prompt 文本",
        "原始 query 文本",
        "原始 user_query 文本",
        "原始 raw_prompt 文本",
        "原始 sql_prompt 文本",
    ):
        assert raw not in text
    assert "[REDACTED_PROMPT]" in text

    reset_runtime_for_test()


def test_export_jsonl_and_limit_cap(monkeypatch):
    reset_runtime_for_test()
    monkeypatch.setattr(settings, "audit_export_enabled", True)
    monkeypatch.setattr(settings, "audit_export_max_rows", 2)
    monkeypatch.setattr(settings, "audit_export_redaction_enabled", True)

    store = get_audit_store()
    for idx in range(3):
        store.append(
            AuditEvent(
                event_type="export_test",
                actor="tester",
                action=f"action_{idx}",
                detail={"token": f"token-{idx}", "request_id": f"req-{idx}"},
            )
        )

    resp = client.get("/audit/events/export", params={"event_type": "export_test", "limit": 10})
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/x-ndjson")
    lines = [line for line in resp.text.splitlines() if line.strip()]
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert all("detail_redacted" in item for item in parsed)
    assert "token-0" not in resp.text

    reset_runtime_for_test()


def test_export_disabled_returns_403(monkeypatch):
    monkeypatch.setattr(settings, "audit_export_enabled", False)
    resp = client.get("/audit/events/export")
    assert resp.status_code == 403
    assert resp.json()["error"] == "audit_export_disabled"


def test_export_redaction_disabled_returns_403(monkeypatch):
    monkeypatch.setattr(settings, "audit_export_enabled", True)
    monkeypatch.setattr(settings, "audit_export_redaction_enabled", False)
    resp = client.get("/audit/events/export")
    assert resp.status_code == 403
    assert resp.json()["error"] == "audit_export_redaction_required"


def test_export_access_when_auth_rbac_disabled(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "rbac_enabled", False)
    monkeypatch.setattr(settings, "audit_export_enabled", True)
    resp = client.get("/audit/events/export")
    assert resp.status_code == 200


def test_export_rbac_roles(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "rbac_enabled", True)
    monkeypatch.setattr(settings, "audit_export_enabled", True)
    monkeypatch.setattr(settings, "jwt_secret", "dev-only-change-me-please-32-bytes")

    viewer_token = _token("viewer", "viewer")
    auditor_token = _token("auditor", "auditor")

    viewer_resp = client.get("/audit/events/export", headers={"Authorization": f"Bearer {viewer_token}"})
    auditor_resp = client.get("/audit/events/export", headers={"Authorization": f"Bearer {auditor_token}"})
    assert viewer_resp.status_code == 403
    assert auditor_resp.status_code == 200

    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "rbac_enabled", False)
