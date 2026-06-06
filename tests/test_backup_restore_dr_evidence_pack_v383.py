from __future__ import annotations

import json
from pathlib import Path

from scripts.backup_restore_dr_evidence_pack import build_backup_restore_dr_evidence_pack


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_dr_env(monkeypatch) -> None:
    for key in [
        "SRE_BACKUP_DRILL_ENABLED",
        "SRE_RESTORE_DRY_RUN_ENABLED",
        "SRE_DR_DRILL_ENABLED",
        "SRE_RTO_MINUTES",
        "SRE_RPO_MINUTES",
        "SRE_BACKUP_SCOPE",
        "SRE_BACKUP_TARGET",
        "SRE_DR_SECONDARY_REGION",
        "DATABASE_URL",
        "REDIS_URL",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_backup_restore_dr_evidence_pack_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_dr_env(monkeypatch)
    summary = build_backup_restore_dr_evidence_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["database_connected"] is False
    assert summary["redis_connected"] is False
    assert summary["backup_executed"] is False
    assert summary["restore_executed"] is False
    assert summary["dr_failover_executed"] is False
    assert payload["version"] == "3.8.0"
    assert payload["phase"] == "v3.8 Phase 18.3"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_backup_restore_dr_evidence_pack_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_dr_env(monkeypatch)
    payload = _read_payload(build_backup_restore_dr_evidence_pack(output_dir=tmp_path / "out"))
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "backup_scope_inventory",
        "deployment_and_migration_boundary",
        "rto_rpo_target_presence",
        "backup_drill_evidence",
        "restore_dry_run_evidence",
        "dr_failover_evidence",
        "runbook_and_failure_diagnostics_linkage",
        "evidence_generation_scripts",
        "regression_test_coverage",
    } <= check_ids


def test_backup_restore_dr_evidence_pack_keeps_skipped_without_dr_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SRE_BACKUP_DRILL_ENABLED", "true")
    monkeypatch.setenv("SRE_RESTORE_DRY_RUN_ENABLED", "true")
    monkeypatch.setenv("SRE_DR_DRILL_ENABLED", "true")
    monkeypatch.setenv("SRE_RTO_MINUTES", "60")
    monkeypatch.setenv("SRE_RPO_MINUTES", "15")

    payload = _read_payload(build_backup_restore_dr_evidence_pack(output_dir=tmp_path / "out"))

    assert payload["status"] == "skipped"
    assert payload["backup_executed"] is False
    assert payload["restore_executed"] is False
    assert payload["dr_failover_executed"] is False
    assert "evidence:backup_drill_report_missing" in payload["missing_conditions"]
    assert "evidence:restore_dry_run_report_missing" in payload["missing_conditions"]
    assert "evidence:dr_failover_report_missing" in payload["missing_conditions"]


def test_backup_restore_dr_evidence_pack_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret-password@example.com/db")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-password@example.com:6379/0")
    monkeypatch.setenv("SRE_BACKUP_TARGET", "s3://bucket/sk-backup-sensitive")

    summary = build_backup_restore_dr_evidence_pack(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "secret-password" not in merged
    assert "redis-password" not in merged
    assert "sk-backup-sensitive" not in merged
    assert "DATABASE_URL" in merged
    assert "REDIS_URL" in merged


def test_backup_restore_dr_evidence_pack_records_local_evidence_without_connections(tmp_path: Path, monkeypatch) -> None:
    _clear_dr_env(monkeypatch)
    payload = _read_payload(build_backup_restore_dr_evidence_pack(output_dir=tmp_path / "out"))

    assert payload["local_checks"]["sqlite_demo_db_script"]["present"] is True
    assert payload["local_checks"]["deployment_guard"]["present"] is True
    assert payload["local_checks"]["backup_restore_checklist"]["present"] is True
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["backup_executed"] is False
