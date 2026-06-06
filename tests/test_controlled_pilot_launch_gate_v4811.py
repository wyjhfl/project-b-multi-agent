from __future__ import annotations

import json
from pathlib import Path

from scripts import controlled_pilot_launch_gate as gate
from scripts.controlled_pilot_launch_gate import build_controlled_pilot_launch_gate


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_ready_sources(root: Path) -> None:
    _write_json(
        root / "bundle" / "001.json",
        {
            "generated_at": "2026-06-05T08:00:00+00:00",
            "status": "success",
            "controlled_pilot_ready": True,
            "final_verification_passed_count": 9,
            "final_verification_requirement_count": 9,
            "missing_condition_count": 0,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
            "go_no_go": {
                "controlled_pilot": "Go",
                "public_production_direct_launch": "No-Go",
                "manual_signoff_required": True,
            },
        },
    )
    _write_json(
        root / "final" / "001.json",
        {
            "generated_at": "2026-06-05T08:00:01+00:00",
            "status": "success",
            "passed_count": 9,
            "requirement_count": 9,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
        },
    )
    _write_json(
        root / "closeout" / "001.json",
        {
            "generated_at": "2026-06-05T08:00:02+00:00",
            "status": "success",
            "final_status": "success",
            "target_record_written": True,
            "missing_conditions": [],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_signed": False,
            "auto_approved": False,
            "auto_closed": False,
        },
    )
    _write_json(
        root / "bootstrap" / "001.json",
        {
            "generated_at": "2026-06-05T08:00:03+00:00",
            "status": "partial",
            "local_service_smoke": {"status": "success"},
            "evidence_count": 17,
            "signoff_closeout_passed": True,
            "final_verification_passed": True,
            "pilot_evidence_bundle_passed": True,
            "operations_console_smoke_status": "skipped",
            "secret_plaintext_output": False,
            "go_no_go": {"public_production_direct_launch": "No-Go"},
        },
    )


def _patch_source_dirs(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(
        gate,
        "SOURCE_DIRS",
        {
            "production_pilot_evidence_bundle": root / "bundle",
            "production_landing_final_verification": root / "final",
            "production_landing_signoff_closeout": root / "closeout",
            "production_pilot_bootstrap": root / "bootstrap",
        },
    )


def test_controlled_pilot_launch_gate_ready_when_all_required_evidence_is_ready(monkeypatch, tmp_path):
    _write_ready_sources(tmp_path)
    _patch_source_dirs(monkeypatch, tmp_path)

    summary = build_controlled_pilot_launch_gate(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "ready"
    assert summary["ready_for_controlled_pilot"] is True
    assert payload["controlled_pilot"] == "Go"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["manual_signoff_required"] is True
    assert payload["missing_condition_count"] == 0
    assert payload["safe_next_action"] == "start_controlled_internal_pilot_window"
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert payload["secret_plaintext_output"] is False


def test_controlled_pilot_launch_gate_blocked_when_evidence_missing(monkeypatch, tmp_path):
    _patch_source_dirs(monkeypatch, tmp_path)

    summary = build_controlled_pilot_launch_gate(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "blocked"
    assert payload["ready_for_controlled_pilot"] is False
    assert payload["controlled_pilot"] == "Manual-Review"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert "controlled_pilot_launch_gate:evidence_bundle_not_go" in payload["missing_conditions"]
    assert "controlled_pilot_launch_gate:final_verification_not_complete" in payload["missing_conditions"]
    assert "controlled_pilot_launch_gate:signoff_closeout_not_complete" in payload["missing_conditions"]


def test_controlled_pilot_launch_gate_blocks_secret_like_source_without_leak(monkeypatch, tmp_path):
    _write_ready_sources(tmp_path)
    _write_json(
        tmp_path / "bundle" / "002.json",
        {
            "generated_at": "2026-06-05T08:01:00+00:00",
            "status": "success",
            "controlled_pilot_ready": True,
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "auto_approved": False,
            "auto_closed": False,
            "go_no_go": {"controlled_pilot": "Go", "public_production_direct_launch": "No-Go"},
            "next_commands": ["token=sk-should-not-leak"],
        },
    )
    _patch_source_dirs(monkeypatch, tmp_path)

    summary = build_controlled_pilot_launch_gate(output_dir=tmp_path / "out")
    payload_text = Path(summary["json_path"]).read_text(encoding="utf-8")
    payload = json.loads(payload_text)

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert "controlled_pilot_launch_gate:secret_plaintext_output_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in payload_text
