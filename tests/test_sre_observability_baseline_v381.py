from __future__ import annotations

import json
from pathlib import Path

from scripts.sre_observability_baseline import build_sre_observability_baseline


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_sre_env(monkeypatch) -> None:
    for key in [
        "SRE_OBSERVABILITY_ENABLED",
        "SRE_APM_ENABLED",
        "SRE_ALERTING_ENABLED",
        "SRE_BACKUP_DRILL_ENABLED",
        "SRE_DR_DRILL_ENABLED",
        "SRE_CAPACITY_TEST_ENABLED",
        "SRE_APM_PROVIDER",
        "SRE_LOG_SINK",
        "SRE_ALERT_CHANNEL",
        "SRE_ONCALL_ROTATION",
        "SRE_RTO_MINUTES",
        "SRE_RPO_MINUTES",
        "SRE_ALERT_WEBHOOK",
        "SRE_APM_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_sre_observability_baseline_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_sre_env(monkeypatch)
    summary = build_sre_observability_baseline(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["external_apm_connected"] is False
    assert summary["alert_sent"] is False
    assert summary["capacity_test_executed"] is False
    assert summary["backup_restore_executed"] is False
    assert summary["dr_failover_executed"] is False
    assert payload["version"] == "3.8.0"
    assert payload["phase"] == "v3.8 Phase 18.1"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_sre_observability_baseline_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_sre_env(monkeypatch)
    summary = build_sre_observability_baseline(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "runtime_metrics_and_cost_api",
        "runtime_snapshot_api",
        "operations_summary_and_acceptance_evidence",
        "audit_export_and_redaction",
        "structured_logging_boundary",
        "failure_diagnostics_pack",
        "backup_restore_and_dr_runbooks",
        "external_apm_tracing_readiness",
        "alerting_slo_oncall_readiness",
        "capacity_backup_dr_drill_gaps",
    } <= check_ids


def test_sre_observability_baseline_partial_when_enterprise_opt_in_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SRE_OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("SRE_APM_ENABLED", "true")
    monkeypatch.setenv("SRE_ALERTING_ENABLED", "true")
    monkeypatch.setenv("SRE_APM_PROVIDER", "placeholder-apm")
    monkeypatch.setenv("SRE_LOG_SINK", "placeholder-log-sink")
    monkeypatch.setenv("SRE_ALERT_CHANNEL", "placeholder-channel")
    monkeypatch.setenv("SRE_ONCALL_ROTATION", "placeholder-oncall")

    summary = build_sre_observability_baseline(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "skipped"
    assert payload["external_apm_connected"] is False
    assert payload["alert_sent"] is False
    assert payload["capacity_test_executed"] is False
    assert payload["backup_restore_executed"] is False
    assert payload["dr_failover_executed"] is False
    assert "evidence:capacity_test_report_missing" in payload["missing_conditions"]


def test_sre_observability_baseline_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SRE_ALERT_CHANNEL", "https://user:password@example.com/webhook")
    monkeypatch.setenv("SRE_ALERT_WEBHOOK", "https://example.com/hook/sk-sensitive-value")
    monkeypatch.setenv("SRE_APM_TOKEN", "sk-apm-sensitive")

    summary = build_sre_observability_baseline(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-sensitive-value" not in merged
    assert "sk-apm-sensitive" not in merged
    assert "password@example" not in merged
    assert "SRE_ALERT_CHANNEL" in merged


def test_sre_observability_baseline_records_local_evidence_without_online_calls(tmp_path: Path, monkeypatch) -> None:
    _clear_sre_env(monkeypatch)
    summary = build_sre_observability_baseline(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["local_checks"]["metrics_api"]["present"] is True
    assert payload["local_checks"]["runtime_snapshot_api"]["present"] is True
    assert payload["local_checks"]["operations_api"]["present"] is True
    assert payload["local_checks"]["failure_diagnostics_script"]["present"] is True
    assert payload["online_endpoints_called"] is False
    assert payload["external_apm_connected"] is False
