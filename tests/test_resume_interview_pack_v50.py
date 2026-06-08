from __future__ import annotations

from pathlib import Path

import scripts.production_landing_text_quality_check as text_quality


ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "docs" / "resume_interview_optimization_pack_v50.md"
RESUME_BLOG_PATH = ROOT / "docs" / "resume_blog_notes.md"
INTERVIEW_GUIDE_PATH = ROOT / "docs" / "interview_guide.md"


def test_resume_interview_optimization_pack_exists_and_matches_current_project_boundary() -> None:
    text = PACK_PATH.read_text(encoding="utf-8")

    assert "简历项目定位" in text
    assert "生产级 Agent Runtime 工程化原型" in text
    assert "受控内网试点" in text
    assert "Operations Command Center" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "不宣称公网生产可直接上线" in text
    assert "真实业务系统暂未接入" in text


def test_resume_interview_optimization_pack_covers_interview_story_and_demo_path() -> None:
    text = PACK_PATH.read_text(encoding="utf-8")

    assert "2 分钟项目讲解" in text
    assert "面试高频追问" in text
    assert "可演示路径" in text
    assert "scripts\\controlled_pilot_demo_landing.ps1" in text
    assert "scripts\\controlled_pilot_console_up.ps1" in text
    assert "Operator Guidance" in text


def test_text_quality_default_targets_include_resume_interview_materials() -> None:
    targets = {path.as_posix() for path in text_quality.DEFAULT_TARGETS}

    assert (text_quality.ROOT_DIR / "docs" / "resume_blog_notes.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "docs" / "interview_guide.md").as_posix() in targets
    assert (
        text_quality.ROOT_DIR / "docs" / "resume_interview_optimization_pack_v50.md"
    ).as_posix() in targets


def test_legacy_resume_and_interview_docs_point_to_v50_source_of_truth() -> None:
    for path in (RESUME_BLOG_PATH, INTERVIEW_GUIDE_PATH):
        text = path.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:16])

        assert "当前以 v5.0 面试主材料为准" in head
        assert "docs/resume_interview_optimization_pack_v50.md" in head
        assert "真实业务系统暂未接入" in head
        assert "public_production_direct_launch=No-Go" in head
        assert "不宣称公网生产可直接上线" in head
