from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_integration_dry_run import build_controlled_integration_dry_run


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_controlled_integration_dry_run_generates_default_checklist(tmp_path: Path) -> None:
    summary = build_controlled_integration_dry_run(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["mode"] == "fake_offline_default"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["integration_count"] == 8
    assert payload["version"] == "3.4.0"
    assert payload["output_dir"] == str(tmp_path / "out")
    assert Path(summary["markdown_path"]).exists()


def test_controlled_integration_dry_run_covers_required_integrations(tmp_path: Path) -> None:
    summary = build_controlled_integration_dry_run(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    ids = {item["integration_id"] for item in payload["integrations"]}

    assert {
        "real_llm",
        "oidc",
        "external_mcp",
        "postgres",
        "redis",
        "frontend_build_network",
        "deployment_guard",
        "audit_export_redaction",
    } <= ids


def test_controlled_integration_missing_real_llm_opt_in_is_skipped(tmp_path: Path, monkeypatch) -> None:
    for key in [
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        "REAL_LLM_MODEL",
        "REAL_LLM_API_KEY_ENV",
    ]:
        monkeypatch.delenv(key, raising=False)

    summary = build_controlled_integration_dry_run(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    real_llm = next(item for item in payload["integrations"] if item["integration_id"] == "real_llm")

    assert real_llm["readiness_status"] == "skipped"
    assert "env:REAL_LLM_API_KEY_ENV" in real_llm["missing_conditions"]
    assert "opt_in:REAL_LLM_SMOKE_ENABLED_not_enabled" in real_llm["missing_conditions"]
    assert payload["real_llm_executed"] is False


def test_controlled_integration_uses_readiness_report_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")
    readiness = tmp_path / "readiness.json"
    _write_json(
        readiness,
        {
            "readiness_status": "partial",
            "version": "3.4.0",
            "mode": "fake_offline_default",
            "read_only": True,
            "real_llm_executed": False,
            "integrations": [
                {
                    "integration_id": "frontend_build_network",
                    "readiness_status": "ready",
                    "missing_conditions": [],
                    "skipped_reasons": [],
                    "read_only": True,
                    "real_llm_executed": False,
                },
                {
                    "integration_id": "real_llm",
                    "readiness_status": "skipped",
                    "missing_conditions": ["REAL_LLM_API_KEY_ENV"],
                    "skipped_reasons": ["REAL_LLM_SMOKE_ENABLED"],
                    "read_only": True,
                    "real_llm_executed": False,
                },
            ],
        },
    )

    summary = build_controlled_integration_dry_run(output_dir=tmp_path / "out", readiness_report=readiness)
    payload = _read_payload(summary)
    frontend = next(item for item in payload["integrations"] if item["integration_id"] == "frontend_build_network")
    real_llm = next(item for item in payload["integrations"] if item["integration_id"] == "real_llm")

    assert payload["readiness_report"]["loaded"] is True
    assert payload["readiness_report"]["metadata"]["integration_count"] == 2
    assert frontend["source_readiness"]["readiness_status"] == "ready"
    assert frontend["readiness_status"] == "ready"
    assert real_llm["readiness_status"] == "skipped"
    assert "REAL_LLM_API_KEY_ENV" in real_llm["missing_conditions"]


def test_controlled_integration_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "local-sensitive-value")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_ENV", "OIDC_CLIENT_SECRET")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "top-secret")
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    key_value = "sk-" + "should-not-leak"
    secret_reason = "api_" + f"key={key_value}"
    readiness = tmp_path / "readiness.json"
    _write_json(
        readiness,
        {
            "readiness_status": "skipped",
            "read_only": True,
            "real_llm_executed": False,
            "api_key": key_value,
            "DATABASE_URL": db_url,
            "integrations": [
                {
                    "integration_id": "postgres",
                    "readiness_status": "skipped",
                    "missing_conditions": [db_url],
                    "skipped_reasons": [secret_reason],
                    "read_only": True,
                    "real_llm_executed": False,
                }
            ],
        },
    )

    summary = build_controlled_integration_dry_run(output_dir=tmp_path / "out", readiness_report=readiness)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["status"] == "blocked"
    assert "readiness_report:secret_like_value_detected" in payload["missing_conditions"]
    assert "local-sensitive-value" not in merged
    assert "top-secret" not in merged
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged
    assert "REAL_LLM_API_KEY_ENV" in merged
    assert "OIDC_CLIENT_SECRET_ENV" in merged
    assert "DATABASE_URL" in merged


def test_controlled_integration_payload_includes_declared_top_level_fields(tmp_path: Path) -> None:
    summary = build_controlled_integration_dry_run(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["external_mcp_connected"] is False
    assert payload["service_started"] is False
    assert payload["default_auth_enabled"] is False
    assert payload["default_rbac_enabled"] is False
    assert payload["default_postgres_enabled"] is False
    assert payload["default_redis_enabled"] is False
    assert "env_presence" in payload
    assert "input_sources" in payload
    assert "go_no_go_hint" in payload
