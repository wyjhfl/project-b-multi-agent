from __future__ import annotations

import json
from pathlib import Path

from scripts.security_regression_compliance_evidence_pack import build_security_regression_compliance_evidence_pack


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_security_env(monkeypatch) -> None:
    for key in [
        "SECURITY_REGRESSION_REVIEW_ENABLED",
        "SECURITY_SCAN_REVIEW_ENABLED",
        "COMPLIANCE_EVIDENCE_REVIEW_ENABLED",
        "AUTH_ENABLED",
        "RBAC_ENABLED",
        "OIDC_ENABLED",
        "SECURITY_HEADERS_ENABLED",
        "REQUEST_SIZE_LIMIT_ENABLED",
        "RATE_LIMIT_ENABLED",
        "ABUSE_GUARD_ENABLED",
        "AUDIT_EXPORT_REDACTION_ENABLED",
        "LOG_REDACTION_ENABLED",
        "JWT_SECRET",
        "DATABASE_URL",
        "REDIS_URL",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_security_regression_compliance_evidence_pack_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_security_env(monkeypatch)
    summary = build_security_regression_compliance_evidence_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["external_security_scan_executed"] is False
    assert summary["formal_security_signoff_recorded"] is False
    assert summary["audit_export_executed"] is False
    assert payload["version"] == "3.9.0"
    assert payload["phase"] == "v3.9 Phase 19.4"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_security_regression_compliance_evidence_pack_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_security_env(monkeypatch)
    payload = _read_payload(build_security_regression_compliance_evidence_pack(output_dir=tmp_path / "out"))
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "prompt_injection_guard_regression",
        "pii_redaction_regression",
        "sql_guard_security_regression",
        "perimeter_guard_regression",
        "auth_rbac_permission_regression",
        "cross_tenant_denial_evidence",
        "audit_export_redaction_regression",
        "release_gate_security_linkage",
        "compliance_evidence_linkage",
        "external_security_scan_and_signoff",
    } <= check_ids


def test_security_regression_compliance_evidence_pack_keeps_skipped_without_signoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SECURITY_REGRESSION_REVIEW_ENABLED", "true")
    monkeypatch.setenv("SECURITY_SCAN_REVIEW_ENABLED", "true")
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_REVIEW_ENABLED", "true")

    payload = _read_payload(build_security_regression_compliance_evidence_pack(output_dir=tmp_path / "out"))

    assert payload["status"] == "skipped"
    assert payload["external_security_scan_executed"] is False
    assert payload["formal_security_signoff_recorded"] is False
    assert "evidence:external_security_scan_report_missing" in payload["missing_conditions"]
    assert "evidence:security_compliance_signoff_missing" in payload["missing_conditions"]


def test_security_regression_compliance_evidence_pack_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "sk-security-secret-sensitive")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret-password@example.com/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-password@example.com:6379/0")

    summary = build_security_regression_compliance_evidence_pack(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-security-secret-sensitive" not in merged
    assert "secret-password" not in merged
    assert "redis-password" not in merged
    assert "JWT_SECRET" in merged
    assert "DATABASE_URL" in merged


def test_security_regression_compliance_evidence_pack_records_local_evidence_without_actions(tmp_path: Path, monkeypatch) -> None:
    _clear_security_env(monkeypatch)
    payload = _read_payload(build_security_regression_compliance_evidence_pack(output_dir=tmp_path / "out"))

    assert payload["local_checks"]["injection_guard"]["present"] is True
    assert payload["local_checks"]["pii_guard"]["present"] is True
    assert payload["local_checks"]["security_headers"]["present"] is True
    assert payload["local_checks"]["audit_tests"]["present"] is True
    assert payload["online_endpoints_called"] is False
    assert payload["external_security_scan_executed"] is False
