from __future__ import annotations

import json
from pathlib import Path

import scripts.production_landing_text_quality_check as text_quality
from scripts.interview_demo_readiness import RESUME_MATERIAL_CHECKS, build_interview_demo_readiness


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_interview_demo_readiness_builds_read_only_resume_interview_report(tmp_path: Path) -> None:
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
    assert payload["operations_command_center_ready"] is True
    assert payload["demo_path_ready"] is True
    assert payload["interview_demo_ready"] is True
    assert payload["missing_conditions"] == []
    assert any(item["id"] == "readme_interview_entry" for item in payload["resume_material_checks"])
    assert "Operations Command Center" in markdown
    assert "public_production_direct_launch=No-Go" in markdown
    assert "真实业务系统暂未接入" in markdown


def test_interview_demo_readiness_exposes_safe_demo_commands(tmp_path: Path) -> None:
    summary = build_interview_demo_readiness(output_dir=tmp_path / "out")
    payload = _payload(summary)

    command_ids = [item["id"] for item in payload["recommended_commands"]]
    assert command_ids == [
        "run_controlled_demo_landing",
        "open_operations_command_center",
        "run_text_quality_check",
        "run_interview_focused_tests",
    ]
    assert all(item["safe_boundary"] == "read_only_no_secret_plaintext" for item in payload["recommended_commands"])
    assert payload["recommended_commands"][0]["command"] == (
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_demo_landing.ps1 "
        "-EnvPath local\\production_landing.staging.env"
    )
    assert payload["recommended_commands"][1]["command"] == (
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_console_up.ps1 "
        "-BackendPort 8000 -FrontendPort 3004"
    )
    assert "sk-" not in json.dumps(payload, ensure_ascii=False)
    assert "tp-" not in json.dumps(payload, ensure_ascii=False)


def test_text_quality_default_targets_include_interview_demo_readiness_files() -> None:
    targets = {path.as_posix() for path in text_quality.DEFAULT_TARGETS}

    assert (text_quality.ROOT_DIR / "docs" / "interview_demo_readiness_v50.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "interview_demo_readiness.py").as_posix() in targets


def test_interview_demo_readiness_requires_legacy_docs_to_point_to_v50_material() -> None:
    for check_id in ("resume_blog_notes", "interview_guide"):
        _, markers = RESUME_MATERIAL_CHECKS[check_id]

        assert "当前以 v5.0 面试主材料为准" in markers
        assert "docs/resume_interview_optimization_pack_v50.md" in markers
        assert "真实业务系统暂未接入" in markers
        assert "public_production_direct_launch=No-Go" in markers
        assert "不宣称公网生产可直接上线" in markers
