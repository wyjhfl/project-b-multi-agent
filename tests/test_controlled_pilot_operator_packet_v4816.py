from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_operator_packet import build_controlled_pilot_operator_packet
from scripts.controlled_pilot_operator_packet import _contains_secret_like


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ready_dirs(root: Path) -> dict[str, Path]:
    dirs = {
        "controlled_pilot_status_summary": root / "status",
        "production_landing_status": root / "landing_status",
        "controlled_pilot_launch_package": root / "package",
        "controlled_pilot_window_record": root / "window",
        "controlled_pilot_window_status": root / "window_status",
        "operations_console_landing_smoke": root / "smoke",
        "business_system_read_smoke": root / "business_smoke",
        "business_system_production_readiness": root / "business_readiness",
    }
    _write_json(
        dirs["controlled_pilot_status_summary"] / "001_controlled_pilot_status_summary.json",
        {
            "generated_at": "2026-06-05T09:00:00+00:00",
            "status": "ready",
            "controlled_internal_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_status"] / "001_production_landing_status.json",
        {
            "generated_at": "2026-06-05T09:00:00+00:00",
            "status": "success",
            "controlled_pilot_ready": True,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_launch_package"] / "001_controlled_pilot_launch_package.json",
        {
            "generated_at": "2026-06-05T09:00:01+00:00",
            "status": "ready",
            "launch_package_ready": True,
            "controlled_pilot": "Go",
            "operator_commands": [
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_status_summary.py"
            ],
            "pilot_roles": [{"role": "operations_owner", "responsibility": "monitor service health"}],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_window_record"] / "001_controlled_pilot_window_record.json",
        {
            "generated_at": "2026-06-05T09:00:02+00:00",
            "status": "opened",
            "opened": True,
            "window_id": "controlled-pilot-2026-06-05",
            "opened_by": "WYJ",
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_window_status"] / "001_controlled_pilot_window_status.json",
        {
            "generated_at": "2026-06-05T09:00:03+00:00",
            "status": "healthy",
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["operations_console_landing_smoke"] / "001_operations_console_landing_smoke.json",
        {
            "generated_at": "2026-06-05T09:00:04+00:00",
            "status": "success",
            "execute": True,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "001_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-05T09:00:05+00:00",
            "status": "skipped",
            "execute": False,
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "env_profile": {
                "auth_mode": "bearer",
                "public_production_gap": True,
                "safe_commands": {
                    "interactive_powershell": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
                },
            },
            "go_no_go": {"public_production_direct_launch": "No-Go"},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "001_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-05T09:00:06+00:00",
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
    return dirs


def test_controlled_pilot_operator_packet_ready(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")

    summary = build_controlled_pilot_operator_packet(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert summary["public_production_direct_launch"] == "No-Go"
    assert summary["window_id"] == "controlled-pilot-2026-06-05"
    assert summary["missing_condition_count"] == 0
    assert summary["secret_plaintext_output"] is False
    assert payload["rollback_required"] is True
    assert payload["external_expansion_requires_new_manual_go_no_go"] is True
    assert payload["operator_commands"]
    assert payload["public_production_gaps"] == [
        "business_system:production_readiness_not_ready",
        "business_system:public_production_gap",
        "business_system:real_read_only_smoke_not_executed",
    ]
    assert payload["business_system_production_readiness"]["status"] == "needs_input"
    assert payload["business_system_production_readiness"]["missing_condition_count"] == 2
    assert payload["business_system_read_smoke"]["auth_mode"] == "bearer"
    assert payload["business_system_read_smoke"]["safe_commands"]["interactive_powershell"].endswith(
        "scripts\\business_system_read_smoke.ps1"
    )
    assert set(payload["evidence_paths"]) == set(dirs)


def test_controlled_pilot_operator_packet_ready_only_when_business_readiness_ready(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    _write_json(
        dirs["controlled_pilot_status_summary"] / "002_controlled_pilot_status_summary.json",
        {
            "generated_at": "2026-06-05T09:30:00+00:00",
            "status": "ready",
            "controlled_internal_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "002_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-05T09:30:05+00:00",
            "status": "success",
            "execute": True,
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "env_profile": {
                "auth_mode": "bearer",
                "public_production_gap": False,
                "safe_commands": {
                    "interactive_powershell": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
                },
            },
            "go_no_go": {"public_production_direct_launch": "No-Go"},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "002_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-05T09:30:06+00:00",
            "status": "ready",
            "missing_condition_count": 0,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_operator_packet(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "ready"
    assert summary["controlled_internal_pilot"] == "Go"
    assert payload["public_production_gaps"] == []


def test_controlled_pilot_operator_packet_secret_detector_allows_managed_placeholders() -> None:
    assert _contains_secret_like({"required_env": ["BUSINESS_SYSTEM_TOKEN=<secret-managed-token>"]}) is False
    assert _contains_secret_like({"required_env": ["BUSINESS_SYSTEM_TOKEN=real-token-value"]}) is True


def test_controlled_pilot_operator_packet_partial_when_window_missing(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    dirs["controlled_pilot_window_record"] = tmp_path / "missing_window"

    summary = build_controlled_pilot_operator_packet(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert "controlled_pilot_window_record:latest_report_missing" in payload["missing_conditions"]


def test_controlled_pilot_operator_packet_partial_when_landing_status_not_ready(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    _write_json(
        dirs["production_landing_status"] / "002_production_landing_status.json",
        {
            "generated_at": "2026-06-05T09:30:00+00:00",
            "status": "partial",
            "controlled_pilot_ready": False,
            "blockers": ["execution_gate:not_allowed"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_operator_packet(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert payload["sources"]["production_landing_status"]["status"] == "partial"


def test_controlled_pilot_operator_packet_blocks_secret_like_source_without_leak(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    _write_json(
        dirs["controlled_pilot_status_summary"] / "002_controlled_pilot_status_summary.json",
        {
            "generated_at": "2026-06-05T09:30:00+00:00",
            "status": "ready",
            "controlled_internal_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "note": "token=sk-should-not-leak",
        },
    )

    summary = build_controlled_pilot_operator_packet(output_dir=tmp_path / "out", report_dirs=dirs)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["controlled_internal_pilot"] == "No-Go"
    assert summary["secret_plaintext_output"] is True
    assert "sk-should-not-leak" not in merged
