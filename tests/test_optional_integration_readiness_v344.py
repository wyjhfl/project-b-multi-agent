from __future__ import annotations

import json
from pathlib import Path

from scripts.optional_integration_readiness import build_optional_integration_readiness


def test_optional_integration_readiness_generates_matrix(tmp_path: Path):
    summary = build_optional_integration_readiness(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["mode"] == "fake_offline_default"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["integration_count"] == 8
    assert Path(summary["markdown_path"]).exists()
    assert payload["version"] == "3.6.0"


def test_optional_integration_readiness_covers_required_integrations(tmp_path: Path):
    summary = build_optional_integration_readiness(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
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


def test_optional_integration_missing_real_opt_in_is_skipped(tmp_path: Path, monkeypatch):
    for key in [
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        "REAL_LLM_MODEL",
        "REAL_LLM_API_KEY_ENV",
    ]:
        monkeypatch.delenv(key, raising=False)

    summary = build_optional_integration_readiness(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    real_llm = next(item for item in payload["integrations"] if item["integration_id"] == "real_llm")

    assert real_llm["readiness_status"] == "skipped"
    assert real_llm["missing_conditions"]
    assert payload["real_llm_executed"] is False


def test_optional_integration_readiness_does_not_leak_secret_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("OIDC_CLIENT_SECRET_ENV", "OIDC_CLIENT_SECRET")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "top-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@localhost/db")

    summary = build_optional_integration_readiness(output_dir=tmp_path / "out")
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    assert "sk-sensitive-value" not in merged
    assert "top-secret" not in merged
    assert "postgresql://demo:secret@" not in merged
    assert "REAL_LLM_API_KEY_ENV" in merged
    assert "OIDC_CLIENT_SECRET_ENV" in merged
