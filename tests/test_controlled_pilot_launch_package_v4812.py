from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_launch_package import build_controlled_pilot_launch_package


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ready_sources(root: Path) -> dict[str, Path]:
    dirs = {
        "controlled_pilot_launch_gate": root / "gate",
        "production_landing_signoff_closeout": root / "closeout",
        "production_landing_final_verification": root / "final",
        "production_pilot_evidence_bundle": root / "bundle",
        "production_pilot_bootstrap": root / "bootstrap",
        "operations_console_landing_smoke": root / "ops_smoke",
    }
    _write_json(
        dirs["controlled_pilot_launch_gate"] / "001.json",
        {
            "generated_at": "2026-06-05T08:00:00+00:00",
            "status": "ready",
            "ready_for_controlled_pilot": True,
            "controlled_pilot": "Go",
            "missing_condition_count": 0,
            "safe_next_action": "start_controlled_internal_pilot_window",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
            "secret_plaintext_output": False,
            "missing_conditions": [],
        },
    )
    _write_json(
        dirs["production_landing_signoff_closeout"] / "001.json",
        {
            "generated_at": "2026-06-05T08:00:01+00:00",
            "status": "success",
            "final_status": "success",
            "target_record_written": True,
            "missing_condition_count": 0,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_final_verification"] / "001.json",
        {
            "generated_at": "2026-06-05T08:00:02+00:00",
            "status": "success",
            "passed_count": 9,
            "requirement_count": 9,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_pilot_evidence_bundle"] / "001.json",
        {
            "generated_at": "2026-06-05T08:00:03+00:00",
            "status": "success",
            "controlled_pilot_ready": True,
            "missing_condition_count": 0,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "go_no_go": {"controlled_pilot": "Go", "public_production_direct_launch": "No-Go"},
        },
    )
    _write_json(
        dirs["production_pilot_bootstrap"] / "001.json",
        {
            "generated_at": "2026-06-05T08:00:04+00:00",
            "status": "partial",
            "evidence_count": 17,
            "signoff_closeout_passed": True,
            "final_verification_passed": True,
            "pilot_evidence_bundle_passed": True,
            "operations_console_smoke_status": "skipped",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["operations_console_landing_smoke"] / "001.json",
        {
            "generated_at": "2026-06-05T08:00:05+00:00",
            "status": "success",
            "execute": True,
            "page_http_status": 200,
            "summary_http_status": 200,
            "secret_plaintext_output": False,
        },
    )
    return dirs


def test_controlled_pilot_launch_package_ready_when_gate_and_required_sources_ready(tmp_path):
    dirs = _ready_sources(tmp_path)

    summary = build_controlled_pilot_launch_package(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "ready"
    assert payload["launch_package_ready"] is True
    assert payload["controlled_pilot"] == "Go"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["manual_signoff_required"] is True
    assert payload["missing_condition_count"] == 0
    assert payload["safe_next_action"] == "open_controlled_pilot_window"
    assert len(payload["operator_commands"]) == 3
    assert len(payload["pilot_roles"]) == 4
    assert payload["launch_window"]["rollback_required"] is True
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert payload["secret_plaintext_output"] is False


def test_controlled_pilot_launch_package_blocked_when_gate_missing(tmp_path):
    dirs = _ready_sources(tmp_path)
    dirs["controlled_pilot_launch_gate"] = tmp_path / "missing_gate"

    summary = build_controlled_pilot_launch_package(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "blocked"
    assert payload["launch_package_ready"] is False
    assert payload["controlled_pilot"] == "Manual-Review"
    assert "controlled_pilot_launch_gate:latest_report_missing" in payload["missing_conditions"]
    assert "controlled_pilot_launch_package:launch_gate_not_ready" in payload["missing_conditions"]


def test_controlled_pilot_launch_package_blocks_secret_like_source_without_leak(tmp_path):
    dirs = _ready_sources(tmp_path)
    _write_json(
        dirs["controlled_pilot_launch_gate"] / "002.json",
        {
            "generated_at": "2026-06-05T08:01:00+00:00",
            "status": "ready",
            "ready_for_controlled_pilot": True,
            "controlled_pilot": "Go",
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
            "secret_plaintext_output": False,
            "operator_command": "token=sk-should-not-leak",
        },
    )

    summary = build_controlled_pilot_launch_package(output_dir=tmp_path / "out", source_dirs=dirs)
    payload_text = Path(summary["json_path"]).read_text(encoding="utf-8")
    payload = json.loads(payload_text)

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert "controlled_pilot_launch_gate:secret_like_text_detected" in payload["missing_conditions"]
    assert "controlled_pilot_launch_package:secret_plaintext_output_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in payload_text
