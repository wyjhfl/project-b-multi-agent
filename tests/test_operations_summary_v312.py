from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app, reset_runtime_for_test

client = TestClient(app)


def test_operations_summary_returns_current_showcase_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("PRODUCTION_LANDING_TEXT_QUALITY_REPORT_DIR", str(tmp_path / "missing_text_quality"))
    monkeypatch.setenv("INTERVIEW_DEMO_READINESS_REPORT_DIR", str(tmp_path / "missing_interview"))
    reset_runtime_for_test()

    response = client.get("/operations/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "read_only"
    assert data["pilot_reports"]["total_reports"] == 0
    assert data["observability"]["current_docs"] == [
        "README.md",
        "docs/architecture.md",
        "docs/api_v1.md",
        "docs/demo_script_v1.md",
        "docs/deployment_runbook.md",
        "docs/interview_guide.md",
        "docs/resume_blog_notes.md",
        "docs/resume_interview_optimization_pack_v50.md",
        "docs/interview_demo_readiness_v50.md",
        "docs/production_policy.md",
    ]
    assert "scripts/interview_demo_readiness.py" in data["observability"]["current_scripts"]
    assert "landing_command_center" in data["observability"]

    command_center = data["observability"]["landing_command_center"]
    assert command_center["mode"] == "read_only_showcase"
    assert command_center["controlled_internal_pilot"] == "Manual-Review"
    assert command_center["controlled_internal_pilot_source"] == "showcase_runtime_summary"
    assert command_center["public_production_direct_launch"] == "No-Go"
    assert command_center["real_business_system_connected"] is False
    assert command_center["business_system_public_production_blocker"] is True
    assert command_center["secret_plaintext_output"] is False
    assert "business_system:real_system_not_connected" in command_center["run_packet_missing_conditions"]
    commands = command_center["operator_guidance"]["commands"]
    assert commands[0]["id"] == "run_interview_readiness"
    assert commands[0]["command"] == "python scripts/interview_demo_readiness.py"
    assert commands[1]["id"] == "start_local_demo"
    assert commands[2]["id"] == "run_demo_smoke"
    assert commands[0]["safe_boundary"] == "read_only_no_secret_plaintext"

    counts = data["observability"]["last_known_report_counts"]
    assert counts["pilot_reports"] == 0
    assert counts["audit_recent_events"] == 0
    assert counts["text_quality_reports"] == 0
    assert counts["interview_demo_readiness_reports"] == 0


def test_operations_summary_counts_current_reports(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "runtime_db_path", str(tmp_path / "runtime.sqlite"))
    monkeypatch.setattr(settings, "metrics_db_path", str(tmp_path / "metrics.sqlite"))
    reset_runtime_for_test()

    pilot_dir = tmp_path / "pilot"
    text_dir = tmp_path / "text"
    interview_dir = tmp_path / "interview"
    for directory in (pilot_dir, text_dir, interview_dir):
        directory.mkdir()

    (pilot_dir / "001.json").write_text(
        json.dumps(
            {
                "report_id": "r1",
                "generated_at": "2026-06-05T00:00:00+00:00",
                "scenario": "nl2sql_preview",
                "outcome": "fallback",
                "request_id": "req-1",
                "fallback_used": True,
                "cost": 0,
                "total_tokens": 0,
            }
        ),
        encoding="utf-8",
    )
    (text_dir / "001.json").write_text(json.dumps({"status": "success", "blocked_file_count": 0}), encoding="utf-8")
    (interview_dir / "001.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")

    monkeypatch.setenv("REAL_LLM_PILOT_REPORT_DIR", str(pilot_dir))
    monkeypatch.setenv("PRODUCTION_LANDING_TEXT_QUALITY_REPORT_DIR", str(text_dir))
    monkeypatch.setenv("INTERVIEW_DEMO_READINESS_REPORT_DIR", str(interview_dir))

    response = client.get("/operations/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["pilot_reports"]["total_reports"] == 1
    assert data["observability"]["last_known_report_counts"]["pilot_reports"] == 1
    assert data["observability"]["last_known_report_counts"]["text_quality_reports"] == 1
    assert data["observability"]["last_known_report_counts"]["interview_demo_readiness_reports"] == 1
    assert data["observability"]["landing_command_center"]["evidence"]["text_quality"]["status"] == "success"
