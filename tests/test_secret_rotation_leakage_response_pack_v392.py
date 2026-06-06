from __future__ import annotations

import json
from pathlib import Path

from scripts.secret_rotation_leakage_response_pack import build_secret_rotation_leakage_response_pack


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_secret_env(monkeypatch) -> None:
    for key in [
        "SECRET_ROTATION_REVIEW_ENABLED",
        "SECRET_LEAKAGE_DRILL_ENABLED",
        "SECRET_REVOCATION_DRILL_ENABLED",
        "JWT_SECRET",
        "DATABASE_URL",
        "REDIS_URL",
        "OIDC_CLIENT_SECRET",
        "REAL_LLM_API_KEY_ENV",
        "MCP_REAL_COMMAND",
        "BUSINESS_SYSTEM_API_KEY_ENV",
        "SRE_ALERT_WEBHOOK",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_secret_rotation_leakage_response_pack_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_secret_env(monkeypatch)
    summary = build_secret_rotation_leakage_response_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["external_secret_system_connected"] is False
    assert summary["secret_rotation_executed"] is False
    assert summary["secret_revocation_executed"] is False
    assert summary["leakage_scan_executed"] is False
    assert payload["version"] == "3.9.0"
    assert payload["phase"] == "v3.9 Phase 19.2"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_secret_rotation_leakage_response_pack_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_secret_env(monkeypatch)
    payload = _read_payload(build_secret_rotation_leakage_response_pack(output_dir=tmp_path / "out"))
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "secret_surface_inventory",
        "redaction_and_audit_boundary",
        "identity_secret_lifecycle",
        "external_integration_secret_boundary",
        "governance_exception_linkage",
        "rotation_drill_evidence",
        "leakage_response_evidence",
        "revocation_and_recovery_evidence",
        "regression_test_coverage",
    } <= check_ids


def test_secret_rotation_leakage_response_pack_keeps_skipped_without_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SECRET_ROTATION_REVIEW_ENABLED", "true")
    monkeypatch.setenv("SECRET_LEAKAGE_DRILL_ENABLED", "true")
    monkeypatch.setenv("SECRET_REVOCATION_DRILL_ENABLED", "true")

    payload = _read_payload(build_secret_rotation_leakage_response_pack(output_dir=tmp_path / "out"))

    assert payload["status"] == "skipped"
    assert payload["secret_rotation_executed"] is False
    assert payload["secret_revocation_executed"] is False
    assert payload["leakage_scan_executed"] is False
    assert "evidence:secret_rotation_drill_report_missing" in payload["missing_conditions"]
    assert "evidence:secret_leakage_response_report_missing" in payload["missing_conditions"]
    assert "evidence:secret_revocation_drill_report_missing" in payload["missing_conditions"]


def test_secret_rotation_leakage_response_pack_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "sk-jwt-secret-sensitive")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret-password@example.com/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-password@example.com:6379/0")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "oidc-client-secret-sensitive")
    monkeypatch.setenv("SRE_ALERT_WEBHOOK", "https://example.com/hook/sk-alert-secret")

    summary = build_secret_rotation_leakage_response_pack(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-jwt-secret-sensitive" not in merged
    assert "secret-password" not in merged
    assert "redis-password" not in merged
    assert "oidc-client-secret-sensitive" not in merged
    assert "sk-alert-secret" not in merged
    assert "JWT_SECRET" in merged
    assert "DATABASE_URL" in merged
    assert "SRE_ALERT_WEBHOOK" in merged


def test_secret_rotation_leakage_response_pack_records_local_evidence_without_actions(tmp_path: Path, monkeypatch) -> None:
    _clear_secret_env(monkeypatch)
    payload = _read_payload(build_secret_rotation_leakage_response_pack(output_dir=tmp_path / "out"))

    assert payload["local_checks"]["env_example"]["present"] is True
    assert payload["local_checks"]["deployment_guard"]["present"] is True
    assert payload["local_checks"]["structured_logging"]["present"] is True
    assert payload["local_checks"]["audit_store"]["present"] is True
    assert payload["online_endpoints_called"] is False
    assert payload["secret_rotation_executed"] is False
