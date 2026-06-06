from __future__ import annotations

import json
from pathlib import Path

from scripts.slo_alerting_runbook_pack import build_slo_alerting_runbook_pack


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_alert_env(monkeypatch) -> None:
    for key in [
        "SRE_ALERTING_ENABLED",
        "SRE_SLO_REVIEW_ENABLED",
        "SRE_ALERT_DRY_RUN_ENABLED",
        "SRE_ONCALL_DRILL_ENABLED",
        "SRE_ALERT_CHANNEL",
        "SRE_ONCALL_ROTATION",
        "SRE_ESCALATION_POLICY",
        "SRE_SLO_AVAILABILITY_TARGET",
        "SRE_SLO_LATENCY_P95_MS",
        "SRE_SLO_ERROR_RATE_PERCENT",
        "SRE_ALERT_WEBHOOK",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_slo_alerting_runbook_pack_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_alert_env(monkeypatch)
    summary = build_slo_alerting_runbook_pack(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["online_endpoints_called"] is False
    assert summary["alert_sent"] is False
    assert summary["oncall_notified"] is False
    assert summary["alert_webhook_called"] is False
    assert payload["version"] == "3.8.0"
    assert payload["phase"] == "v3.8 Phase 18.2"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_slo_alerting_runbook_pack_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_alert_env(monkeypatch)
    payload = _read_payload(build_slo_alerting_runbook_pack(output_dir=tmp_path / "out"))
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "slo_sli_source_inventory",
        "slo_target_configuration",
        "structured_logging_for_alert_context",
        "alert_severity_and_routing",
        "oncall_and_escalation_readiness",
        "alert_dry_run_evidence",
        "incident_runbook_linkage",
        "evidence_generation_scripts",
        "regression_test_coverage",
    } <= check_ids


def test_slo_alerting_runbook_pack_keeps_skipped_without_dry_run_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SRE_ALERTING_ENABLED", "true")
    monkeypatch.setenv("SRE_SLO_REVIEW_ENABLED", "true")
    monkeypatch.setenv("SRE_ALERT_DRY_RUN_ENABLED", "true")
    monkeypatch.setenv("SRE_ONCALL_DRILL_ENABLED", "true")
    monkeypatch.setenv("SRE_ALERT_CHANNEL", "placeholder-channel")
    monkeypatch.setenv("SRE_ONCALL_ROTATION", "placeholder-oncall")
    monkeypatch.setenv("SRE_ESCALATION_POLICY", "placeholder-escalation")

    payload = _read_payload(build_slo_alerting_runbook_pack(output_dir=tmp_path / "out"))

    assert payload["status"] == "skipped"
    assert payload["alert_sent"] is False
    assert payload["oncall_notified"] is False
    assert payload["alert_webhook_called"] is False
    assert "evidence:alert_dry_run_report_missing" in payload["missing_conditions"]
    assert "evidence:oncall_escalation_drill_report_missing" in payload["missing_conditions"]


def test_slo_alerting_runbook_pack_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SRE_ALERT_CHANNEL", "https://user:password@example.com/webhook")
    monkeypatch.setenv("SRE_ALERT_WEBHOOK", "https://example.com/hook/sk-alert-sensitive")

    summary = build_slo_alerting_runbook_pack(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-alert-sensitive" not in merged
    assert "password@example" not in merged
    assert "SRE_ALERT_CHANNEL" in merged
    assert "SRE_ALERT_WEBHOOK" in merged


def test_slo_alerting_runbook_pack_records_local_evidence_without_online_calls(tmp_path: Path, monkeypatch) -> None:
    _clear_alert_env(monkeypatch)
    payload = _read_payload(build_slo_alerting_runbook_pack(output_dir=tmp_path / "out"))

    assert payload["local_checks"]["metrics_api"]["present"] is True
    assert payload["local_checks"]["runtime_snapshot_api"]["present"] is True
    assert payload["local_checks"]["operations_api"]["present"] is True
    assert payload["local_checks"]["sre_baseline_script"]["present"] is True
    assert payload["online_endpoints_called"] is False
    assert payload["alert_sent"] is False
