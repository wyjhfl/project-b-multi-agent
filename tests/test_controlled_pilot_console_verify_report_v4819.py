from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_console_verify_report import build_controlled_pilot_console_verify_report


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_success_reports(root: Path) -> None:
    _write_json(
        root
        / "operations_console_landing_smoke"
        / "2026-06-05T10-00-00_abc_operations_console_landing_smoke.json",
        {
            "status": "success",
            "generated_at": "2026-06-05T10:00:00+00:00",
            "execute": True,
            "checks": {"page_http_status": 200, "summary_http_status": 200},
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        root
        / "controlled_pilot_operator_packet"
        / "2026-06-05T10-00-01_abc_controlled_pilot_operator_packet.json",
        {
            "status": "ready",
            "generated_at": "2026-06-05T10:00:01+00:00",
            "controlled_internal_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "missing_condition_count": 0,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        root
        / "controlled_pilot_status_summary"
        / "2026-06-05T10-00-02_abc_controlled_pilot_status_summary.json",
        {
            "status": "ready",
            "generated_at": "2026-06-05T10:00:02+00:00",
            "controlled_internal_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )


def test_controlled_pilot_console_verify_report_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    _seed_success_reports(report_root)
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_verify_report.REPORTS",
        {
            "operations_console_landing_smoke": (
                report_root / "operations_console_landing_smoke",
                "*_operations_console_landing_smoke.json",
            ),
            "controlled_pilot_operator_packet": (
                report_root / "controlled_pilot_operator_packet",
                "*_controlled_pilot_operator_packet.json",
            ),
            "controlled_pilot_status_summary": (
                report_root / "controlled_pilot_status_summary",
                "*_controlled_pilot_status_summary.json",
            ),
        },
    )
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_verify_report.CONSOLE_RUNTIME_DIR",
        report_root / "controlled_pilot_console",
    )

    summary = build_controlled_pilot_console_verify_report(output_dir=tmp_path / "out")

    assert summary["status"] == "success"
    assert summary["controlled_internal_pilot"] == "Go"
    assert summary["public_production_direct_launch"] == "No-Go"
    assert summary["missing_condition_count"] == 0
    assert summary["secret_plaintext_output"] is False
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_controlled_pilot_console_verify_report_blocks_failed_smoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    _seed_success_reports(report_root)
    _write_json(
        report_root
        / "operations_console_landing_smoke"
        / "2026-06-05T10-00-03_abc_operations_console_landing_smoke.json",
        {
            "status": "failed",
            "generated_at": "2026-06-05T10:00:03+00:00",
            "execute": True,
            "checks": {"page_http_status": 200, "summary_http_status": 500},
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_verify_report.REPORTS",
        {
            "operations_console_landing_smoke": (
                report_root / "operations_console_landing_smoke",
                "*_operations_console_landing_smoke.json",
            ),
            "controlled_pilot_operator_packet": (
                report_root / "controlled_pilot_operator_packet",
                "*_controlled_pilot_operator_packet.json",
            ),
            "controlled_pilot_status_summary": (
                report_root / "controlled_pilot_status_summary",
                "*_controlled_pilot_status_summary.json",
            ),
        },
    )

    summary = build_controlled_pilot_console_verify_report(output_dir=tmp_path / "out")

    assert summary["status"] == "partial"
    assert summary["controlled_internal_pilot"] == "Manual-Review"
    assert "operations_console_landing_smoke:not_usable" in summary["missing_conditions"]
    assert "operations_console_landing_smoke:summary_http_status_not_200" in summary["missing_conditions"]
    assert summary["public_production_direct_launch"] == "No-Go"


def test_controlled_pilot_console_verify_report_redacts_secret_like_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    _seed_success_reports(report_root)
    _write_json(
        report_root
        / "controlled_pilot_operator_packet"
        / "2026-06-05T10-00-03_abc_controlled_pilot_operator_packet.json",
        {
            "status": "ready",
            "generated_at": "2026-06-05T10:00:03+00:00",
            "controlled_internal_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "leaked_value": "tp-abcdefghijklmnopqrstuvwxyz123456",
            "secret_plaintext_output": False,
        },
    )
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_verify_report.REPORTS",
        {
            "operations_console_landing_smoke": (
                report_root / "operations_console_landing_smoke",
                "*_operations_console_landing_smoke.json",
            ),
            "controlled_pilot_operator_packet": (
                report_root / "controlled_pilot_operator_packet",
                "*_controlled_pilot_operator_packet.json",
            ),
            "controlled_pilot_status_summary": (
                report_root / "controlled_pilot_status_summary",
                "*_controlled_pilot_status_summary.json",
            ),
        },
    )

    summary = build_controlled_pilot_console_verify_report(output_dir=tmp_path / "out")
    output_text = Path(summary["json_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert summary["controlled_internal_pilot"] == "No-Go"
    assert summary["secret_plaintext_output"] is True
    assert "tp-abcdefghijklmnopqrstuvwxyz123456" not in output_text


def test_controlled_pilot_console_verify_report_can_force_failed_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_root = tmp_path / "reports"
    _seed_success_reports(report_root)
    monkeypatch.setattr(
        "scripts.controlled_pilot_console_verify_report.REPORTS",
        {
            "operations_console_landing_smoke": (
                report_root / "operations_console_landing_smoke",
                "*_operations_console_landing_smoke.json",
            ),
            "controlled_pilot_operator_packet": (
                report_root / "controlled_pilot_operator_packet",
                "*_controlled_pilot_operator_packet.json",
            ),
            "controlled_pilot_status_summary": (
                report_root / "controlled_pilot_status_summary",
                "*_controlled_pilot_status_summary.json",
            ),
        },
    )

    summary = build_controlled_pilot_console_verify_report(
        output_dir=tmp_path / "out",
        forced_status="failed",
        failure_reason="operations_console_landing_smoke.py failed with exit code 1",
    )

    assert summary["status"] == "failed"
    assert summary["controlled_internal_pilot"] == "No-Go"
    assert summary["public_production_direct_launch"] == "No-Go"
    assert summary["failure_reason"] == "operations_console_landing_smoke.py failed with exit code 1"
    assert "verify_script:operations_console_landing_smoke.py failed with exit code 1" in summary["missing_conditions"]
