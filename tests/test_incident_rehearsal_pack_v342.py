from __future__ import annotations

import json
from pathlib import Path

from scripts.incident_rehearsal_pack import STATUS_VOCABULARY, build_incident_rehearsal_pack


def test_incident_rehearsal_pack_generates_json_and_markdown(tmp_path: Path):
    summary = build_incident_rehearsal_pack(
        output_dir=tmp_path / "incident",
        base_url="http://127.0.0.1:65530",
        run_compose_checks=False,
    )

    assert summary["status"] in STATUS_VOCABULARY
    assert summary["mode"] == "fake_offline_default"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False
    assert summary["scenario_count"] >= 13
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()

    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    assert payload["generated_at"]
    assert payload["commit"]
    assert payload["version"] == "3.5.0"
    assert payload["status_vocabulary"] == STATUS_VOCABULARY


def test_incident_rehearsal_pack_covers_required_scenarios(tmp_path: Path):
    summary = build_incident_rehearsal_pack(output_dir=tmp_path / "incident", base_url="http://127.0.0.1:65530")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    names = {item["name"] for item in payload["scenarios"]}

    assert {
        "service_unavailable",
        "docker_compose_config_failure",
        "prod_compose_missing_required_env",
        "deployment_check_ok_false",
        "operations_unavailable_or_empty",
        "acceptance_snapshot_online_skipped",
        "demo_e2e_online_smoke_skipped",
        "failure_diagnostics_blocked_findings",
        "report_index_empty_or_stale_candidates",
        "config_drift_warnings",
        "governance_or_live_drill_skipped",
        "oidc_secret_env_missing",
        "real_llm_opt_in_missing_or_skipped",
    } <= names


def test_incident_rehearsal_missing_opt_in_is_skipped_not_success(tmp_path: Path, monkeypatch):
    for key in [
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        "REAL_LLM_MODEL",
        "REAL_LLM_API_KEY_ENV",
        "OIDC_ENABLED",
        "OIDC_ISSUER_URL",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET_ENV",
        "OIDC_REDIRECT_URI",
    ]:
        monkeypatch.delenv(key, raising=False)

    summary = build_incident_rehearsal_pack(output_dir=tmp_path / "incident", base_url="http://127.0.0.1:65530")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    by_name = {item["name"]: item for item in payload["scenarios"]}

    assert by_name["real_llm_opt_in_missing_or_skipped"]["status"] == "skipped"
    assert by_name["oidc_secret_env_missing"]["status"] == "skipped"
    assert payload["real_llm_executed"] is False


def test_incident_rehearsal_no_secret_plaintext_leak(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-value")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "top-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@localhost/db")

    summary = build_incident_rehearsal_pack(output_dir=tmp_path / "incident", base_url="http://127.0.0.1:65530")
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    assert "sk-sensitive-value" not in merged
    assert "top-secret" not in merged
    assert "postgresql://demo:secret@" not in merged
