from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_status_summary import build_controlled_pilot_status_summary


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ready_dirs(root: Path) -> dict[str, Path]:
    dirs = {
        "production_pilot_bootstrap": root / "bootstrap",
        "production_pilot_evidence_bundle": root / "bundle",
        "controlled_pilot_launch_gate": root / "gate",
        "controlled_pilot_launch_package": root / "package",
        "controlled_pilot_window_status": root / "window_status",
        "operations_console_landing_smoke": root / "ops_smoke",
        "business_system_read_smoke": root / "business_smoke",
        "business_system_production_readiness": root / "business_readiness",
        "production_landing_evidence_freshness": root / "evidence_freshness",
    }
    _write_json(
        dirs["production_pilot_bootstrap"] / "001_production_pilot_bootstrap.json",
        {
            "generated_at": "2026-06-05T09:00:00+00:00",
            "status": "partial",
            "operations_console_smoke_status": "success",
            "runtime_smoke_passed": True,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_pilot_evidence_bundle"] / "001_production_pilot_evidence_bundle.json",
        {
            "generated_at": "2026-06-05T09:00:01+00:00",
            "status": "success",
            "controlled_pilot_ready": True,
            "go_no_go": {"controlled_pilot": "Go", "public_production_direct_launch": "No-Go"},
            "missing_condition_count": 0,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_launch_gate"] / "001_controlled_pilot_launch_gate.json",
        {
            "generated_at": "2026-06-05T09:00:02+00:00",
            "status": "ready",
            "ready_for_controlled_pilot": True,
            "controlled_pilot": "Go",
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_launch_package"] / "001_controlled_pilot_launch_package.json",
        {
            "generated_at": "2026-06-05T09:00:03+00:00",
            "status": "ready",
            "launch_package_ready": True,
            "controlled_pilot": "Go",
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_window_status"] / "001_controlled_pilot_window_status.json",
        {
            "generated_at": "2026-06-05T09:00:04+00:00",
            "status": "healthy",
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["operations_console_landing_smoke"] / "001_operations_console_landing_smoke.json",
        {
            "generated_at": "2026-06-05T09:00:05+00:00",
            "status": "success",
            "execute": True,
            "page_http_status": 200,
            "summary_http_status": 200,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "001_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-05T09:00:06+00:00",
            "status": "skipped",
            "execute": False,
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "env_profile": {"public_production_gap": True},
            "go_no_go": {"public_production_direct_launch": "No-Go"},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "001_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-05T09:00:07+00:00",
            "status": "needs_input",
            "missing_condition_count": 2,
            "missing_conditions": [
                "owner:operations_owner_missing",
                "evidence:business_system_real_read_smoke_not_executed",
            ],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_evidence_freshness"] / "001_production_landing_evidence_freshness.json",
        {
            "generated_at": "2026-06-05T09:00:08+00:00",
            "status": "success",
            "worktree_clean": True,
            "source_count": 8,
            "stale_source_count": 0,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    return dirs


def test_controlled_pilot_status_summary_ready_with_successful_executed_smoke(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path)

    summary = build_controlled_pilot_status_summary(report_dirs=dirs, write_report=False)

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert summary["public_production_direct_launch"] == "No-Go"
    assert summary["secret_plaintext_output"] is False
    assert summary["blocking_reports"] == []
    assert summary["public_production_gaps"] == [
        "business_system:production_readiness_not_ready",
        "business_system:public_production_gap",
        "business_system:real_read_only_smoke_not_executed",
    ]
    assert summary["reports"]["operations_console_landing_smoke"]["selection"] == "latest_successful_executed"


def test_controlled_pilot_status_summary_ready_only_when_business_readiness_ready(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path)
    _write_json(
        dirs["business_system_read_smoke"] / "002_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-05T09:30:06+00:00",
            "status": "success",
            "execute": True,
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "env_profile": {"public_production_gap": False},
            "go_no_go": {"public_production_direct_launch": "No-Go"},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "002_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-05T09:30:07+00:00",
            "status": "ready",
            "missing_condition_count": 0,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_status_summary(report_dirs=dirs, write_report=False)

    assert summary["status"] == "ready"
    assert summary["controlled_internal_pilot"] == "Go"
    assert summary["public_production_gaps"] == []


def test_controlled_pilot_status_summary_uses_successful_execute_over_newer_skipped(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path)
    _write_json(
        dirs["operations_console_landing_smoke"] / "002_operations_console_landing_smoke.json",
        {
            "generated_at": "2026-06-05T09:30:00+00:00",
            "status": "skipped",
            "execute": False,
            "missing_conditions": ["cli:--execute_not_requested"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_status_summary(report_dirs=dirs, write_report=False)

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert summary["reports"]["operations_console_landing_smoke"]["status"] == "success"
    assert summary["reports"]["operations_console_landing_smoke"]["generated_at"] == "2026-06-05T09:00:05+00:00"


def test_controlled_pilot_status_summary_partial_when_required_report_missing(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path)
    dirs["controlled_pilot_launch_package"] = tmp_path / "missing_package"

    summary = build_controlled_pilot_status_summary(report_dirs=dirs, write_report=False)

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert "controlled_pilot_launch_package" in summary["blocking_reports"]


def test_controlled_pilot_status_summary_partial_when_evidence_freshness_stale(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path)
    _write_json(
        dirs["business_system_read_smoke"] / "002_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-05T09:30:06+00:00",
            "status": "success",
            "execute": True,
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "env_profile": {"public_production_gap": False},
            "go_no_go": {"public_production_direct_launch": "No-Go"},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "002_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-05T09:30:07+00:00",
            "status": "ready",
            "missing_condition_count": 0,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_evidence_freshness"] / "002_production_landing_evidence_freshness.json",
        {
            "generated_at": "2026-06-05T09:30:08+00:00",
            "status": "partial",
            "worktree_clean": False,
            "source_count": 8,
            "stale_source_count": 1,
            "missing_conditions": ["git:worktree_dirty"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_status_summary(report_dirs=dirs, write_report=False)

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert "production_landing_evidence_freshness" in summary["blocking_reports"]
    freshness = summary["reports"]["production_landing_evidence_freshness"]
    assert freshness["worktree_clean"] is False
    assert freshness["stale_source_count"] == 1


def test_controlled_pilot_status_summary_writes_report(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    summary = build_controlled_pilot_status_summary(
        report_dirs=dirs,
        output_dir=tmp_path / "out",
    )
    json_path = Path(summary["json_path"])
    markdown_path = Path(summary["markdown_path"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    merged_text = json_path.read_text(encoding="utf-8") + markdown_path.read_text(encoding="utf-8")

    assert summary["status"] == "partial"
    assert json_path.exists()
    assert markdown_path.exists()
    assert payload["controlled_internal_pilot"] == "Manual-Review"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False
    assert payload["public_production_gap_count"] == 3
    assert "business_system:production_readiness_not_ready" in merged_text
    assert "business_system:real_read_only_smoke_not_executed" in merged_text
    assert "sk-" not in merged_text
