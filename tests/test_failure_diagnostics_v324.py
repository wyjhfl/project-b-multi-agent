from __future__ import annotations

import json
from pathlib import Path

from scripts.failure_diagnostics import build_failure_diagnostics


def test_failure_diagnostics_generates_json_and_markdown(tmp_path: Path):
    summary = build_failure_diagnostics(
        output_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        run_compose_checks=False,
    )

    json_path = Path(summary["json_path"])
    md_path = Path(summary["markdown_path"])
    assert json_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["report_id"]
    assert payload["generated_at"]
    assert payload["mode"] == "fake_offline_default"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert "scenarios" in payload
    assert "docker_compose_config" in payload["scenarios"]
    assert "prod_compose_missing_required_env" in payload["scenarios"]


def test_failure_diagnostics_service_unavailable_marked_skipped(tmp_path: Path):
    summary = build_failure_diagnostics(
        output_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        run_compose_checks=False,
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert payload["online_checks"]["status"] in {"skipped", "partial", "ok"}
    if payload["online_checks"]["status"] == "skipped":
        assert payload["online_checks"]["reason"] == "service_unavailable"
        assert payload["scenarios"]["operations_service_unavailable"]["status"] == "skipped"


def test_failure_diagnostics_redacts_sensitive_values_and_prompt(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:super-secret@localhost:5432/demo")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret-value")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "gpt-4o-mini")

    summary = build_failure_diagnostics(
        output_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        run_compose_checks=False,
    )
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    forbidden = [
        "sk-sensitive-value",
        "postgresql://demo:super-secret@",
        "redis://:redis-secret@",
        "jwt-secret-value",
        "raw_prompt",
        "sql_prompt",
    ]
    for text in forbidden:
        assert text not in merged


def test_failure_diagnostics_placeholder_not_counted_as_real_secret(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("JWT_SECRET", "placeholder-jwt-secret")
    monkeypatch.setenv("DATABASE_URL", "placeholder-database-url")
    monkeypatch.setenv("REDIS_URL", "placeholder-redis-url")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "placeholder-model")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder-api-key")

    summary = build_failure_diagnostics(
        output_dir=tmp_path,
        base_url="http://127.0.0.1:65530",
        run_compose_checks=False,
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    prod_check = payload["scenarios"]["prod_compose_missing_required_env"]
    real_llm_check = payload["scenarios"]["real_llm_opt_in_skipped"]

    assert prod_check["status"] == "warning"
    assert "JWT_SECRET" in prod_check["placeholder_env"]
    assert "DATABASE_URL" in prod_check["placeholder_env"]
    assert "REDIS_URL" in prod_check["placeholder_env"]

    assert real_llm_check["status"] == "warning"
    assert "OPENAI_API_KEY" in real_llm_check["placeholder_env"]
    assert real_llm_check["real_llm_executed"] is False
