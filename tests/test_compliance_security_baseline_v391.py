from __future__ import annotations

import json
from pathlib import Path

from scripts.compliance_security_baseline import build_compliance_security_baseline


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_compliance_env(monkeypatch) -> None:
    for key in [
        "COMPLIANCE_SECURITY_REVIEW_ENABLED",
        "COMPLIANCE_AUDIT_REVIEW_ENABLED",
        "COMPLIANCE_RELEASE_GATE_REVIEW_ENABLED",
        "COMPLIANCE_SECRET_ROTATION_REVIEW_ENABLED",
        "APP_ENV",
        "AUTH_ENABLED",
        "RBAC_ENABLED",
        "OIDC_ENABLED",
        "AUDIT_RETENTION_ENABLED",
        "AUDIT_EXPORT_REDACTION_ENABLED",
        "STRUCTURED_LOGGING_ENABLED",
        "LOG_REDACTION_ENABLED",
        "SECURITY_HEADERS_ENABLED",
        "REQUEST_SIZE_LIMIT_ENABLED",
        "RATE_LIMIT_ENABLED",
        "ABUSE_GUARD_ENABLED",
        "JWT_SECRET",
        "DATABASE_URL",
        "REDIS_URL",
        "OIDC_CLIENT_SECRET",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_compliance_security_baseline_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_compliance_env(monkeypatch)
    summary = build_compliance_security_baseline(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["external_system_connected"] is False
    assert summary["security_scan_executed"] is False
    assert summary["audit_export_executed"] is False
    assert summary["secret_rotation_executed"] is False
    assert summary["release_or_rollback_executed"] is False
    assert payload["version"] == "3.9.0"
    assert payload["phase"] == "v3.9 Phase 19.1"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_compliance_security_baseline_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_compliance_env(monkeypatch)
    payload = _read_payload(build_compliance_security_baseline(output_dir=tmp_path / "out"))
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "deployment_gate_and_release_boundary",
        "security_headers_request_guards",
        "audit_logging_retention_redaction",
        "identity_rbac_oidc_boundary",
        "permission_and_cross_tenant_evidence",
        "prompt_pii_guardrail_security",
        "compliance_documentation_baseline",
        "formal_review_and_signoff",
        "secret_rotation_readiness",
        "regression_test_coverage",
    } <= check_ids


def test_compliance_security_baseline_keeps_skipped_without_signoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COMPLIANCE_SECURITY_REVIEW_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_AUDIT_REVIEW_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_RELEASE_GATE_REVIEW_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_SECRET_ROTATION_REVIEW_ENABLED", "true")

    payload = _read_payload(build_compliance_security_baseline(output_dir=tmp_path / "out"))

    assert payload["status"] == "skipped"
    assert payload["security_scan_executed"] is False
    assert payload["audit_export_executed"] is False
    assert payload["secret_rotation_executed"] is False
    assert "evidence:formal_compliance_signoff_missing" in payload["missing_conditions"]
    assert "evidence:secret_rotation_drill_report_missing" in payload["missing_conditions"]


def test_compliance_security_baseline_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "sk-jwt-sensitive-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret-password@example.com/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-password@example.com:6379/0")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "client-secret-sensitive")

    summary = build_compliance_security_baseline(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-jwt-sensitive-value" not in merged
    assert "secret-password" not in merged
    assert "redis-password" not in merged
    assert "client-secret-sensitive" not in merged
    assert "JWT_SECRET" in merged
    assert "DATABASE_URL" in merged
    assert "OIDC_CLIENT_SECRET" in merged


def test_compliance_security_baseline_records_local_evidence_without_actions(tmp_path: Path, monkeypatch) -> None:
    _clear_compliance_env(monkeypatch)
    payload = _read_payload(build_compliance_security_baseline(output_dir=tmp_path / "out"))

    assert payload["local_checks"]["deployment_guard"]["present"] is True
    assert payload["local_checks"]["security_headers"]["present"] is True
    assert payload["local_checks"]["audit_store"]["present"] is True
    assert payload["local_checks"]["security_injection_guard"]["present"] is True
    assert payload["online_endpoints_called"] is False
    assert payload["release_or_rollback_executed"] is False
