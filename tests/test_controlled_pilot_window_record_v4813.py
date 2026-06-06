from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_window_record import build_controlled_pilot_window_record


def _write_launch_package(path: Path, *, secret: bool = False) -> None:
    payload = {
        "generated_at": "2026-06-05T08:20:00+00:00",
        "status": "ready",
        "launch_package_ready": True,
        "controlled_pilot": "Go",
        "public_production_direct_launch": "No-Go",
        "missing_condition_count": 0,
        "missing_conditions": [],
        "safe_next_action": "open_controlled_pilot_window",
        "operator_commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_launch_package.py"],
        "pilot_roles": [{"role": "release_manager", "responsibility": "confirm launch"}],
        "sources": {"controlled_pilot_launch_gate": {"status": "ready"}},
        "secret_plaintext_output": False,
    }
    if secret:
        payload["operator_commands"].append("token=sk-should-not-leak")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_controlled_pilot_window_record_skipped_without_manual_confirm(tmp_path):
    package = tmp_path / "package.json"
    _write_launch_package(package)

    summary = build_controlled_pilot_window_record(
        output_dir=tmp_path / "out",
        launch_package_path=package,
        window_id="pilot-window-001",
        opened_by="WYJ",
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "skipped"
    assert payload["opened"] is False
    assert payload["window_id"] == "pilot-window-001"
    assert payload["opened_by"] == "WYJ"
    assert payload["confirm_open"] == "not_confirmed"
    assert "controlled_pilot_window_record:confirm_open_not_yes" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False


def test_controlled_pilot_window_record_opened_with_manual_confirm(tmp_path):
    package = tmp_path / "package.json"
    _write_launch_package(package)

    summary = build_controlled_pilot_window_record(
        output_dir=tmp_path / "out",
        launch_package_path=package,
        window_id="pilot-window-002",
        opened_by="WYJ",
        confirm_open="YES",
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "opened"
    assert payload["opened"] is True
    assert payload["controlled_pilot"] == "Go"
    assert payload["missing_condition_count"] == 0
    assert payload["rollback_required"] is True
    assert payload["external_expansion_requires_new_manual_go_no_go"] is True
    assert payload["secret_plaintext_output"] is False


def test_controlled_pilot_window_record_blocked_when_package_missing(tmp_path):
    summary = build_controlled_pilot_window_record(
        output_dir=tmp_path / "out",
        launch_package_path=tmp_path / "missing.json",
        confirm_open="YES",
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "blocked"
    assert payload["opened"] is False
    assert "controlled_pilot_launch_package:latest_report_missing" in payload["missing_conditions"]
    assert "controlled_pilot_window_record:launch_package_not_ready" in payload["missing_conditions"]


def test_controlled_pilot_window_record_blocks_secret_like_package_without_leak(tmp_path):
    package = tmp_path / "package.json"
    _write_launch_package(package, secret=True)

    summary = build_controlled_pilot_window_record(
        output_dir=tmp_path / "out",
        launch_package_path=package,
        confirm_open="YES",
    )
    payload_text = Path(summary["json_path"]).read_text(encoding="utf-8")
    payload = json.loads(payload_text)

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert "controlled_pilot_window_record:secret_like_text_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in payload_text
