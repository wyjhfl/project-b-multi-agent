from __future__ import annotations

import json
from pathlib import Path

from scripts.acceptance_snapshot import build_acceptance_snapshot
from scripts.config_drift_check import build_config_drift_report
from scripts.demo_artifact_bundle import build_demo_artifact_bundle
from scripts.evidence_archive_manifest import build_evidence_archive_manifest
from scripts.failure_diagnostics import build_failure_diagnostics
from scripts.governance_policy_summary import build_governance_policy_summary
from scripts.incident_rehearsal_pack import build_incident_rehearsal_pack
from scripts.optional_integration_readiness import build_optional_integration_readiness
from scripts.pilot_handoff_checklist import build_pilot_handoff_checklist
from scripts.operator_workflow_index import build_operator_workflow_index
from scripts.report_index import build_report_index


COMMON_SUMMARY_KEYS = {"status", "generated_at", "commit", "mode", "read_only", "real_llm_executed", "output_dir"}


def _assert_common(summary: dict):
    for key in COMMON_SUMMARY_KEYS:
        assert key in summary
    assert summary["mode"] == "fake_offline_default"
    assert summary["read_only"] is True
    assert summary["real_llm_executed"] is False


def test_acceptance_snapshot_summary_common_keys(tmp_path: Path):
    summary = build_acceptance_snapshot(output_dir=tmp_path / "acceptance", base_url="http://127.0.0.1:65530")
    _assert_common(summary)
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_demo_artifact_bundle_summary_common_keys(tmp_path: Path):
    run_dir = tmp_path / "artifact_run"
    online_payload = {
        "generated_at": "2026-05-30T00:00:00+00:00",
        "base_url": "http://127.0.0.1:65530",
        "status": "skipped",
        "reason": "service_unavailable",
        "checks": {},
    }
    seed_payload = {"status": "skipped", "reason": "skip_seed_switch"}
    summary = build_demo_artifact_bundle(
        artifact_dir=tmp_path / "artifacts",
        base_url="http://127.0.0.1:65530",
        seed_summary=seed_payload,
        online_smoke_result=online_payload,
        artifact_run_dir=run_dir,
        pilot_report_dir=run_dir / "pilot_reports",
    )
    _assert_common(summary)
    assert Path(summary["summary_path"]).exists()


def test_failure_report_index_config_governance_common_keys(tmp_path: Path):
    failure = build_failure_diagnostics(output_dir=tmp_path / "failure", base_url="http://127.0.0.1:65530", run_compose_checks=False)
    report = build_report_index(output_dir=tmp_path / "report_index")
    drift = build_config_drift_report(output_dir=tmp_path / "config_drift")
    governance = build_governance_policy_summary(output_dir=tmp_path / "governance")
    operator = build_operator_workflow_index(output_dir=tmp_path / "operator_workflow")
    incident = build_incident_rehearsal_pack(
        output_dir=tmp_path / "incident_rehearsal",
        base_url="http://127.0.0.1:65530",
        run_compose_checks=False,
    )
    evidence = build_evidence_archive_manifest(
        output_dir=tmp_path / "evidence_archive",
        evidence_roots={"acceptance_snapshot": tmp_path / "acceptance_empty"},
    )
    optional = build_optional_integration_readiness(output_dir=tmp_path / "optional_integration")
    handoff = build_pilot_handoff_checklist(output_dir=tmp_path / "pilot_handoff")

    for summary in (failure, report, drift, governance, operator, incident, evidence, optional, handoff):
        _assert_common(summary)

    assert Path(failure["json_path"]).exists()
    assert Path(report["json_path"]).exists()
    assert Path(drift["json_path"]).exists()
    assert Path(operator["json_path"]).exists()
    assert Path(incident["json_path"]).exists()
    assert Path(evidence["json_path"]).exists()
    assert Path(optional["json_path"]).exists()
    assert Path(handoff["json_path"]).exists()
    assert (tmp_path / "governance").exists()

    gov_json = Path(governance["json_path"])
    if not gov_json.is_absolute():
        gov_json = Path.cwd() / governance["json_path"]
    payload = json.loads(gov_json.read_text(encoding="utf-8"))
    assert payload["real_llm_executed"] is False
