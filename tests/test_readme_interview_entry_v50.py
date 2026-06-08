from __future__ import annotations

from pathlib import Path


README = Path("README.md")


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    next_heading = text.find("\n## ", start + len(heading))
    return text[start:] if next_heading == -1 else text[start:next_heading]


def test_readme_has_interview_quick_entry_before_historical_phase_notes() -> None:
    text = _readme_text()

    assert "# Project B" in text
    assert "## 面试快速入口（当前推荐阅读）" in text
    assert "## 项目定位" in text
    assert "## 架构总览" in text
    assert text.index("## 面试快速入口（当前推荐阅读）") < text.index("## 项目定位")
    assert "## v3.7 Phase 17.4" not in text
    assert len(text) < 16000


def test_readme_interview_quick_entry_points_to_demo_and_resume_materials() -> None:
    section = _section(_readme_text(), "## 面试快速入口（当前推荐阅读）")

    assert "生产级 Agent Runtime 工程化原型" in section
    assert "docs/resume_interview_optimization_pack_v50.md" in section
    assert "docs/interview_demo_readiness_v50.md" in section
    assert "scripts\\interview_demo_readiness.py" in section
    assert "scripts\\controlled_pilot_demo_landing.ps1" in section
    assert "scripts\\controlled_pilot_console_up.ps1" in section
    assert "http://127.0.0.1:3004/operations" in section
    assert "Operations Command Center" in section


def test_readme_interview_quick_entry_keeps_boundaries_explicit() -> None:
    section = _section(_readme_text(), "## 面试快速入口（当前推荐阅读）")

    assert "public_production_direct_launch=No-Go" in section
    assert "真实业务系统暂未接入" in section
    assert "不宣称公网生产可直接上线" in section
    assert "不宣称真实业务系统生产验收完成" in section
    assert "sk-" not in section
    assert "tp-" not in section


def test_readme_is_github_showcase_ready_without_secret_or_local_artifact_guidance() -> None:
    text = _readme_text()

    required_tokens = [
        "生产级 Agent Runtime 工程化原型",
        "Tool Gateway",
        "PolicyEngine",
        "HITL 审批恢复",
        "Audit",
        "Operations Command Center",
        "pytest",
        "npm run build",
        "docker compose config",
    ]
    for token in required_tokens:
        assert token in text

    forbidden_tokens = [
        "docs/reports/",
        "frontend/node_modules",
        "local/production_landing.staging.env 中保存密钥",
        "sk-",
        "tp-",
    ]
    for token in forbidden_tokens:
        assert token not in text
