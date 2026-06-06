from __future__ import annotations

import json
from pathlib import Path

from scripts import controlled_pilot_window_status_snapshot as snapshot
from scripts.controlled_pilot_window_status_snapshot import build_controlled_pilot_window_status_snapshot


def _write_window(path: Path, *, opened: bool = True, secret: bool = False) -> None:
    payload = {
        "generated_at": "2026-06-05T08:30:00+00:00",
        "status": "opened" if opened else "skipped",
        "window_id": "controlled-pilot-test",
        "opened": opened,
        "opened_by": "WYJ",
        "controlled_pilot": "Go" if opened else "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "missing_conditions": [] if opened else ["controlled_pilot_window_record:confirm_open_not_yes"],
        "missing_condition_count": 0 if opened else 1,
        "rollback_required": True,
        "launch_package": {
            "present": True,
            "status": "ready",
            "launch_package_ready": True,
            "controlled_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "missing_condition_count": 0,
            "safe_next_action": "open_controlled_pilot_window",
            "secret_plaintext_output": False,
        },
        "secret_plaintext_output": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }
    if secret:
        payload["token"] = "sk-should-not-leak"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _ok_operations() -> dict:
    return {
        "status": "success",
        "http_status": 200,
        "missing_conditions": [],
        "health_status": "ok",
        "deployment_ok": True,
        "deployment_error_count": 0,
        "deployment_warning_count": 0,
        "controlled_pilot_window_status": "opened",
        "controlled_pilot_window_opened": True,
        "controlled_pilot_window_id": "controlled-pilot-test",
        "launch_package_status": "ready",
        "launch_package_ready": True,
        "launch_gate_status": "ready",
        "launch_gate_ready": True,
        "public_production_direct_launch": "No-Go",
    }


def test_controlled_pilot_window_status_snapshot_healthy_when_window_open_and_operations_ok(monkeypatch, tmp_path):
    window = tmp_path / "window.json"
    _write_window(window)
    monkeypatch.setattr(snapshot, "_collect_operations_summary", _ok_operations)

    summary = build_controlled_pilot_window_status_snapshot(output_dir=tmp_path / "out", window_record_path=window)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "healthy"
    assert payload["window"]["opened"] is True
    assert payload["window"]["window_id"] == "controlled-pilot-test"
    assert payload["operations_summary"]["health_status"] == "ok"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["missing_condition_count"] == 0
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False


def test_controlled_pilot_window_status_snapshot_degraded_when_window_not_opened(monkeypatch, tmp_path):
    window = tmp_path / "window.json"
    _write_window(window, opened=False)
    monkeypatch.setattr(snapshot, "_collect_operations_summary", _ok_operations)

    summary = build_controlled_pilot_window_status_snapshot(output_dir=tmp_path / "out", window_record_path=window)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "degraded"
    assert payload["window"]["opened"] is False
    assert "controlled_pilot_window_status:window_not_opened" in payload["missing_conditions"]


def test_controlled_pilot_window_status_snapshot_blocked_on_secret_without_leak(monkeypatch, tmp_path):
    window = tmp_path / "window.json"
    _write_window(window, secret=True)
    monkeypatch.setattr(snapshot, "_collect_operations_summary", _ok_operations)

    summary = build_controlled_pilot_window_status_snapshot(output_dir=tmp_path / "out", window_record_path=window)
    payload_text = Path(summary["json_path"]).read_text(encoding="utf-8")
    payload = json.loads(payload_text)

    assert summary["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert "controlled_pilot_window_status:secret_like_text_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in payload_text
