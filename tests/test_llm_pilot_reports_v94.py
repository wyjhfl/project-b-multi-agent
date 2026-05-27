from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _write_report(base: Path, report_id: str, *, prompt_text: str = "原始 prompt 文本") -> None:
    payload = {
        "report_id": report_id,
        "generated_at": "2026-05-27T00:00:00+00:00",
        "provider": "litellm",
        "model": "gpt-4o-mini",
        "scenario": "nl2sql_preview",
        "outcome": "fallback",
        "request_id": "req-v94",
        "real_call_attempted": True,
        "real_call_succeeded": False,
        "fallback_used": True,
        "fallback_reason": "budget_blocked",
        "budget_action": "fallback",
        "cache_hit": False,
        "latency_ms": 9.9,
        "prompt_tokens": 11,
        "completion_tokens": 4,
        "total_tokens": 15,
        "cost": 0.07,
        "error_type": "budget_block",
        "api_key": "sk-test-secret",
        "detail": {
            "prompt": prompt_text,
            "query": "原始 query 文本",
            "password": "db-password",
            "database_url": "postgresql://user:dbpassword@localhost:5432/db",
            "redis_url": "redis://:redispassword@localhost:6379/0",
        },
    }
    path = base / f"2026-05-27_{report_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_reports_list_should_return_empty_when_dir_not_exists(monkeypatch, tmp_path):
    missing = tmp_path / "missing"
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(missing))
    response = client.get("/llm/pilot/reports")
    assert response.status_code == 200
    assert response.json() == []


def test_reports_list_should_read_from_tmp_path(monkeypatch, tmp_path):
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    _write_report(tmp_path, "pilot-report-1")

    response = client.get("/llm/pilot/reports")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["report_id"] == "pilot-report-1"
    assert payload[0]["request_id"] == "req-v94"


def test_report_detail_should_be_redacted(monkeypatch, tmp_path):
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    _write_report(tmp_path, "pilot-report-2")

    response = client.get("/llm/pilot/reports/pilot-report-2")
    assert response.status_code == 200
    payload = response.json()
    text = json.dumps(payload, ensure_ascii=False)
    assert payload["prompt_tokens"] == 11
    assert payload["detail"]["prompt"] == "[REDACTED_PROMPT]"
    assert "sk-test-secret" not in text
    assert "原始 query 文本" not in text
    assert "db-password" not in text
    assert "dbpassword" not in text
    assert "redispassword" not in text


def test_path_traversal_should_be_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    response = client.get("/llm/pilot/reports/a..b")
    assert response.status_code == 400


def test_markdown_should_not_leak_sensitive_text(monkeypatch, tmp_path):
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    _write_report(tmp_path, "pilot-report-3")
    response = client.get("/llm/pilot/reports/pilot-report-3/markdown")
    assert response.status_code == 200
    text = response.text
    assert "原始 prompt 文本" not in text
    assert "sk-test-secret" not in text
    assert "dbpassword" not in text


def test_report_not_found_should_return_404(monkeypatch, tmp_path):
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path))
    response = client.get("/llm/pilot/reports/not-found")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "pilot_report_not_found"
