from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app, reset_runtime_for_test
from app.models.schemas import AuditEvent, TaskRun, TaskStatus

client = TestClient(app)


def _write_report(base: Path, report_id: str) -> None:
    payload = {
        "report_id": report_id,
        "generated_at": "2026-05-27T00:00:00+00:00",
        "provider": "litellm",
        "model": "gpt-4o-mini",
        "scenario": "nl2sql_preview",
        "outcome": "fallback",
        "request_id": "req-op-001",
        "fallback_used": True,
        "prompt_tokens": 9,
        "completion_tokens": 3,
        "total_tokens": 12,
        "cost": 0.06,
        "detail": {
            "prompt": "原始 prompt 文本",
            "api_key": "sk-secret",
            "password": "db-password",
            "database_url": "postgresql://user:dbpassword@localhost:5432/db",
            "redis_url": "redis://:redispassword@localhost:6379/0",
        },
    }
    path = base / f"2026-05-27_{report_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_operations_summary_should_return_empty_states_when_report_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path / "missing"))

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "read_only"
    assert data["pilot_reports"]["directory_exists"] is False
    assert data["pilot_reports"]["total_reports"] == 0
    assert data["pilot_reports"]["reports"] == []
    text = json.dumps(data, ensure_ascii=False)
    for raw in ("sk-secret", "dbpassword", "redispassword", "原始 prompt 文本"):
        assert raw not in text


def test_operations_summary_should_include_safe_aggregates(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    _write_report(tmp_path, "ops-report-1")

    from app.main import get_approval_store, get_audit_store, get_metrics_recorder, get_task_store

    task_store = get_task_store()
    task_store.save_task(
        TaskRun(task_id="task_ops_1", query="demo task", status=TaskStatus.completed),
        mode="keyword",
    )

    approval_store = get_approval_store()
    approval_store.create_approval(
        task_id="task_ops_1",
        tool_name="demo_tool",
        action="demo_action",
        payload={"query": "原始 query 文本", "token": "approval-token"},
    )

    audit_store = get_audit_store()
    audit_store.append(
        AuditEvent(
            event_type="ops_summary_test",
            action="view_operations",
            detail={"prompt": "原始 prompt 文本", "token": "audit-token", "request_id": "req-aud-001"},
        )
    )

    metrics = get_metrics_recorder()
    metrics.record_task(task_id="task_ops_1", mode="keyword", status="completed", latency_ms=12.0)
    metrics.record_token_usage(task_id="task_ops_1", prompt_tokens=21, completion_tokens=8, cost=0.11)

    response = client.get("/operations/summary")
    assert response.status_code == 200
    data = response.json()
    text = json.dumps(data, ensure_ascii=False)

    assert data["health"]["version"] == "3.1.0"
    assert data["task_approval"]["task_count"] >= 1
    assert data["task_approval"]["approval_count"] >= 1
    assert data["pilot_reports"]["directory_exists"] is True
    assert data["pilot_reports"]["total_reports"] >= 1
    assert data["pilot_reports"]["reports"][0]["report_id"] == "ops-report-1"
    assert data["runtime_metrics"]["total_prompt_tokens"] >= 21
    assert data["runtime_metrics"]["total_cost"] >= 0.11
    assert data["audit"]["event_count"] >= 1
    assert "[REDACTED_PROMPT]" in text
    for raw in ("原始 prompt 文本", "sk-secret", "dbpassword", "redispassword", "approval-token", "audit-token"):
        assert raw not in text
