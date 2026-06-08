from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_run_packet import build_controlled_pilot_run_packet


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ready_dirs(root: Path) -> dict[str, Path]:
    dirs = {
        "controlled_pilot_delivery_gate": root / "delivery",
        "controlled_pilot_launch_gate": root / "launch_gate",
        "controlled_pilot_launch_package": root / "launch_package",
        "controlled_pilot_status_summary": root / "status_summary",
        "controlled_pilot_operator_packet": root / "operator_packet",
        "controlled_pilot_console_verify": root / "console_verify",
        "production_landing_refresh_status": root / "refresh_status",
        "production_landing_status": root / "landing_status",
        "business_system_read_smoke": root / "business_smoke",
    }
    _write_json(
        dirs["controlled_pilot_delivery_gate"] / "001_controlled_pilot_delivery_gate.json",
        {
            "generated_at": "2026-06-08T09:00:00+00:00",
            "status": "success",
            "controlled_pilot_delivery_ready": True,
            "enterprise_landing_scope": "controlled_internal_pilot",
            "accepted_remaining_gaps": ["business_system:real_business_system_required"],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_launch_gate"] / "001_controlled_pilot_launch_gate.json",
        {
            "generated_at": "2026-06-08T09:00:01+00:00",
            "status": "ready",
            "ready_for_controlled_pilot": True,
            "controlled_pilot": "Go",
            "accepted_remaining_gaps": ["business_system:real_business_system_required"],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "manual_signoff_required": True,
        },
    )
    _write_json(
        dirs["controlled_pilot_launch_package"] / "001_controlled_pilot_launch_package.json",
        {
            "generated_at": "2026-06-08T09:00:02+00:00",
            "status": "ready",
            "launch_package_ready": True,
            "controlled_pilot": "Go",
            "accepted_remaining_gaps": ["business_system:real_business_system_required"],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "launch_window": {
                "scope": "controlled_internal_pilot",
                "rollback_required": True,
                "external_expansion_requires_new_manual_go_no_go": True,
                "public_production_direct_launch": "No-Go",
            },
            "operator_commands": [
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_console_verify.ps1"
            ],
        },
    )
    _write_json(
        dirs["controlled_pilot_status_summary"] / "001_controlled_pilot_status_summary.json",
        {
            "generated_at": "2026-06-08T09:00:03+00:00",
            "status": "ready",
            "controlled_internal_pilot": "Go",
            "accepted_remaining_gaps": ["business_system:real_business_system_required"],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_operator_packet"] / "001_controlled_pilot_operator_packet.json",
        {
            "generated_at": "2026-06-08T09:00:04+00:00",
            "status": "ready",
            "controlled_internal_pilot": "Go",
            "accepted_remaining_gaps": ["business_system:real_business_system_required"],
            "public_production_gaps": [
                "business_system:production_readiness_not_ready",
                "business_system:public_production_gap",
            ],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "rollback_required": True,
            "external_expansion_requires_new_manual_go_no_go": True,
        },
    )
    _write_json(
        dirs["controlled_pilot_console_verify"] / "001_controlled_pilot_console_verify.json",
        {
            "generated_at": "2026-06-08T09:00:05+00:00",
            "status": "success",
            "controlled_internal_pilot": "Go",
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_refresh_status"] / "001_production_landing_refresh_status.json",
        {
            "generated_at": "2026-06-08T09:00:06+00:00",
            "status": "partial",
            "final_status": "partial",
            "blocker_count": 1,
            "final_blockers": ["business_system:real_business_system_required"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_status"] / "001_production_landing_status.json",
        {
            "generated_at": "2026-06-08T09:00:07+00:00",
            "status": "partial",
            "execution_allowed": True,
            "ready_domain_count": 5,
            "domain_count": 5,
            "blockers": ["business_system:real_business_system_required"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "real_llm": {
                "status": "success",
                "real_llm_executed": True,
                "network_check_executed": True,
                "api_key_present": True,
            },
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "001_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-08T09:00:08+00:00",
            "status": "success",
            "execute": True,
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "demo_business_system_used": True,
            "real_business_system_connected": False,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    return dirs


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_controlled_pilot_run_packet_ready_with_demo_business_gap(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")

    summary = build_controlled_pilot_run_packet(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "ready"
    assert summary["run_packet_ready"] is True
    assert summary["controlled_internal_pilot"] == "Go"
    assert summary["public_production_direct_launch"] == "No-Go"
    assert summary["missing_condition_count"] == 0
    assert summary["secret_plaintext_output"] is False
    assert payload["ready_scope"] == "controlled_internal_pilot"
    assert payload["accepted_remaining_gaps"] == ["business_system:real_business_system_required"]
    assert payload["real_production_remaining_gaps"] == ["business_system:real_business_system_required"]
    assert payload["business_system_boundary"]["demo_business_system_used"] is True
    assert payload["business_system_boundary"]["real_business_system_connected"] is False
    assert payload["business_system_boundary"]["business_data_written"] is False
    assert payload["safety_boundary"]["rollback_required"] is True
    assert payload["safety_boundary"]["external_expansion_requires_new_manual_go_no_go"] is True
    assert payload["operator_commands"]["verify_console"].endswith("scripts\\controlled_pilot_console_verify.ps1")
    assert payload["operator_commands"]["rollback_console"].endswith("scripts\\controlled_pilot_console_down.ps1")
    assert set(payload["evidence_paths"]) == set(dirs)


def test_controlled_pilot_run_packet_prefers_latest_successful_business_smoke_over_newer_skipped(
    tmp_path: Path,
) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    _write_json(
        dirs["business_system_read_smoke"] / "999_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-08T10:00:00+00:00",
            "status": "skipped",
            "execute": False,
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "demo_business_system_used": False,
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_run_packet(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "ready"
    assert payload["business_system_boundary"]["demo_business_system_used"] is True
    assert payload["sources"]["business_system_read_smoke"]["status"] == "success"
    assert payload["evidence_paths"]["business_system_read_smoke"].endswith("001_business_system_read_smoke.json")


def test_controlled_pilot_run_packet_blocks_secret_like_source_without_leak(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    _write_json(
        dirs["controlled_pilot_status_summary"] / "002_controlled_pilot_status_summary.json",
        {
            "generated_at": "2026-06-08T09:01:00+00:00",
            "status": "ready",
            "controlled_internal_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "note": "token=sk-should-not-leak",
        },
    )

    summary = build_controlled_pilot_run_packet(output_dir=tmp_path / "out", source_dirs=dirs)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["run_packet_ready"] is False
    assert summary["controlled_internal_pilot"] == "No-Go"
    assert summary["secret_plaintext_output"] is True
    assert "sk-should-not-leak" not in merged


def test_controlled_pilot_run_packet_blocks_public_production_boundary_change(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    _write_json(
        dirs["controlled_pilot_launch_gate"] / "002_controlled_pilot_launch_gate.json",
        {
            "generated_at": "2026-06-08T09:01:00+00:00",
            "status": "ready",
            "ready_for_controlled_pilot": True,
            "controlled_pilot": "Go",
            "accepted_remaining_gaps": ["business_system:real_business_system_required"],
            "missing_condition_count": 0,
            "public_production_direct_launch": "Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_run_packet(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert summary["controlled_internal_pilot"] == "No-Go"
    assert "controlled_pilot_run_packet:public_production_boundary_changed" in payload["missing_conditions"]


def test_controlled_pilot_run_packet_partial_when_console_verify_missing(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    dirs["controlled_pilot_console_verify"] = tmp_path / "missing_console_verify"

    summary = build_controlled_pilot_run_packet(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert summary["run_packet_ready"] is False
    assert "controlled_pilot_console_verify:latest_report_missing" in payload["missing_conditions"]


def test_controlled_pilot_run_packet_includes_upstream_missing_conditions_for_manual_review(tmp_path: Path) -> None:
    dirs = _ready_dirs(tmp_path / "sources")
    _write_json(
        dirs["controlled_pilot_operator_packet"] / "002_controlled_pilot_operator_packet.json",
        {
            "generated_at": "2026-06-08T09:01:00+00:00",
            "status": "partial",
            "controlled_internal_pilot": "Manual-Review",
            "accepted_remaining_gaps": ["business_system:real_business_system_required"],
            "missing_conditions": ["production_landing_evidence_freshness:not_fresh"],
            "missing_condition_count": 1,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "rollback_required": True,
            "external_expansion_requires_new_manual_go_no_go": True,
        },
    )

    summary = build_controlled_pilot_run_packet(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert summary["run_packet_ready"] is False
    assert "controlled_pilot_operator_packet:production_landing_evidence_freshness:not_fresh" in payload[
        "missing_conditions"
    ]
    assert "controlled_pilot_run_packet:required_ready_evidence_not_satisfied" in payload["missing_conditions"]
