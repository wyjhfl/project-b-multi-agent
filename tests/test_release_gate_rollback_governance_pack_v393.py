from __future__ import annotations

import json
from pathlib import Path

from scripts.release_gate_rollback_governance_pack import build_release_gate_rollback_governance_pack


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_release_env(monkeypatch) -> None:
    for key in [
        "RELEASE_GATE_REVIEW_ENABLED",
        "RELEASE_ROLLBACK_DRILL_ENABLED",
        "RELEASE_CHANGE_APPROVAL_ENABLED",
        "APP_ENV",
        "STORAGE_BACKEND",
        "AUTH_ENABLED",
        "RBAC_ENABLED",
        "OIDC_ENABLED",
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_SECRET",
        "RELEASE_FREEZE_WINDOW",
        "RELEASE_APPROVER",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_release_gate_rollback_governance_pack_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_release_env(monkeypatch)
    summary = build_release_gate_rollback_governance_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["release_executed"] is False
    assert summary["rollback_executed"] is False
    assert summary["migration_executed"] is False
    assert summary["tag_created"] is False
    assert payload["version"] == "3.9.0"
    assert payload["phase"] == "v3.9 Phase 19.3"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_release_gate_rollback_governance_pack_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_release_env(monkeypatch)
    payload = _read_payload(build_release_gate_rollback_governance_pack(output_dir=tmp_path / "out"))
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "deployment_gate_inventory",
        "release_artifact_readiness",
        "deployment_and_migration_precheck",
        "change_approval_evidence",
        "release_gate_signoff_evidence",
        "rollback_drill_evidence",
        "rollback_runbook_linkage",
        "governance_security_linkage",
        "regression_test_coverage",
    } <= check_ids


def test_release_gate_rollback_governance_pack_keeps_skipped_without_signoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RELEASE_GATE_REVIEW_ENABLED", "true")
    monkeypatch.setenv("RELEASE_ROLLBACK_DRILL_ENABLED", "true")
    monkeypatch.setenv("RELEASE_CHANGE_APPROVAL_ENABLED", "true")

    payload = _read_payload(build_release_gate_rollback_governance_pack(output_dir=tmp_path / "out"))

    assert payload["status"] == "skipped"
    assert payload["release_executed"] is False
    assert payload["rollback_executed"] is False
    assert payload["tag_created"] is False
    assert "evidence:release_change_approval_record_missing" in payload["missing_conditions"]
    assert "evidence:release_gate_signoff_missing" in payload["missing_conditions"]
    assert "evidence:rollback_drill_report_missing" in payload["missing_conditions"]


def test_release_gate_rollback_governance_pack_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "sk-release-secret-sensitive")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret-password@example.com/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-password@example.com:6379/0")

    summary = build_release_gate_rollback_governance_pack(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-release-secret-sensitive" not in merged
    assert "secret-password" not in merged
    assert "redis-password" not in merged
    assert "JWT_SECRET" in merged
    assert "DATABASE_URL" in merged


def test_release_gate_rollback_governance_pack_records_local_evidence_without_actions(tmp_path: Path, monkeypatch) -> None:
    _clear_release_env(monkeypatch)
    payload = _read_payload(build_release_gate_rollback_governance_pack(output_dir=tmp_path / "out"))

    assert payload["local_checks"]["deployment_guard"]["present"] is True
    assert payload["local_checks"]["docker_compose"]["present"] is True
    assert payload["local_checks"]["release_review_v38"]["present"] is True
    assert payload["online_endpoints_called"] is False
    assert payload["release_executed"] is False
