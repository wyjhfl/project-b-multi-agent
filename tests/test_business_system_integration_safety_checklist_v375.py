from __future__ import annotations

import json
from pathlib import Path

from scripts.business_system_integration_safety_checklist import build_business_system_integration_safety_checklist


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_business_env(monkeypatch) -> None:
    for key in [
        "BUSINESS_INTEGRATION_ENABLED",
        "BUSINESS_INTEGRATION_READ_ONLY",
        "BUSINESS_INTEGRATION_WRITE_ENABLED",
        "BUSINESS_INTEGRATION_APPROVAL_REQUIRED",
        "BUSINESS_INTEGRATION_AUDIT_REQUIRED",
        "BUSINESS_SYSTEM_NAME",
        "BUSINESS_SYSTEM_BASE_URL_ENV",
        "BUSINESS_SYSTEM_TOKEN_ENV",
        "BUSINESS_SYSTEM_BASE_URL",
        "BUSINESS_SYSTEM_TOKEN",
        "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
        "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
        "BUSINESS_SYSTEM_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_business_system_safety_checklist_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_business_env(monkeypatch)
    summary = build_business_system_integration_safety_checklist(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["business_system_connected"] is False
    assert summary["business_read_executed"] is False
    assert summary["business_write_executed"] is False
    assert payload["version"] == "3.7.0"
    assert payload["phase"] == "v3.7 Phase 17.5"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_business_system_safety_checklist_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_business_env(monkeypatch)
    summary = build_business_system_integration_safety_checklist(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "business_integration_opt_in",
        "tool_gateway_policy_boundary",
        "tool_allowlist_and_timeout",
        "write_boundary_and_idempotency",
        "approval_resume_boundary",
        "audit_evidence_boundary",
        "request_guard_and_prompt_safety",
        "failure_recovery_and_rollback_evidence",
    } <= check_ids


def test_business_system_safety_checklist_partial_when_opt_in_config_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESS_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_READ_ONLY", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_WRITE_ENABLED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_APPROVAL_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_AUDIT_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOOL_ALLOWLIST", "erp_read,crm_lookup")
    monkeypatch.setenv("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST", "erp_update")
    monkeypatch.setenv("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "10")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_BASE_URL")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN_ENV", "BUSINESS_SYSTEM_TOKEN")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", "placeholder-not-a-url")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", "placeholder-not-secret")

    summary = build_business_system_integration_safety_checklist(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "skipped"
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["approval_bypassed"] is False
    assert payload["audit_bypassed"] is False
    assert "evidence:rollback_runbook_not_provided" in payload["missing_conditions"]


def test_business_system_safety_checklist_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_BASE_URL")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN_ENV", "BUSINESS_SYSTEM_TOKEN")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", "https://user:password@example.com/api")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", "sk-sensitive-value")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOOL_ALLOWLIST", "erp_read")

    summary = build_business_system_integration_safety_checklist(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-sensitive-value" not in merged
    assert "password@example" not in merged
    assert "BUSINESS_SYSTEM_TOKEN_ENV" in merged
    assert "BUSINESS_SYSTEM_TOKEN" in merged


def test_business_system_safety_checklist_records_local_evidence_without_business_calls(tmp_path: Path, monkeypatch) -> None:
    _clear_business_env(monkeypatch)
    summary = build_business_system_integration_safety_checklist(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["local_checks"]["tool_gateway"]["present"] is True
    assert payload["local_checks"]["policy_engine"]["present"] is True
    assert payload["local_checks"]["approval_api"]["present"] is True
    assert payload["local_checks"]["audit_api"]["present"] is True
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False
    assert payload["business_write_executed"] is False
