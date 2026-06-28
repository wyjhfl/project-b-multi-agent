from __future__ import annotations

import json
from pathlib import Path

from scripts.interview_demo_readiness import RESUME_MATERIAL_CHECKS, build_interview_demo_readiness


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_interview_demo_readiness_builds_read_only_showcase_report(tmp_path: Path) -> None:
    summary = build_interview_demo_readiness(output_dir=tmp_path / "out")
    payload = _payload(summary)
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "success"
    assert payload["status"] == "success"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["real_business_system_connected"] is False
    assert payload["business_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["resume_material_ready"] is True
    assert payload["frontend_ready"] is True
    assert payload["demo_path_ready"] is True
    assert payload["interview_demo_ready"] is True
    assert payload["missing_conditions"] == []
    assert any(item["id"] == "readme" for item in payload["resume_material_checks"])
    assert "面试演示就绪检查" in markdown
    assert "public_production_direct_launch: No-Go" in markdown


def test_interview_demo_readiness_exposes_current_safe_demo_commands(tmp_path: Path) -> None:
    summary = build_interview_demo_readiness(output_dir=tmp_path / "out")
    payload = _payload(summary)

    command_ids = [item["id"] for item in payload["recommended_commands"]]
    assert command_ids == [
        "run_interview_readiness",
        "start_local_demo",
        "run_demo_smoke",
        "run_focused_tests",
    ]
    assert payload["recommended_commands"][0]["command"] == "python scripts/interview_demo_readiness.py"
    assert payload["recommended_commands"][1]["command"] == (
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo_up.ps1"
    )
    merged = json.dumps(payload, ensure_ascii=False)
    assert "codex_python.ps1" not in merged
    assert "controlled_pilot_console_up.ps1" not in merged
    assert "production_landing_text_quality_check.py" not in merged
    assert "sk-" not in merged
    assert "tp-" not in merged


def test_interview_demo_readiness_material_markers_are_current_utf8() -> None:
    _, markers = RESUME_MATERIAL_CHECKS["readme"]

    assert "Multi-Agent Runtime" in markers
    assert "Trajectory" in markers
    assert "public_production_direct_launch" in markers
