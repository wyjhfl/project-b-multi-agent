from __future__ import annotations

from pathlib import Path


OBSERVABILITY_PAGE = Path("frontend/src/app/observability/page.tsx")
GLOBAL_CSS = Path("frontend/src/app/globals.css")
OBSERVABILITY_API = Path("frontend/src/lib/api/observability.ts")


def test_observability_page_surfaces_multi_agent_trajectory() -> None:
    text = OBSERVABILITY_PAGE.read_text(encoding="utf-8")

    assert "Multi-Agent 轨迹" in text
    assert "getTaskTrajectory" in text
    assert "trajectory.summary.roles" in text
    assert "trajectory.summary.selected_mode" in text
    assert "trajectory.summary.executed_mode" in text
    assert "trajectory.steps.map" in text


def test_observability_trajectory_api_client_exists() -> None:
    text = OBSERVABILITY_API.read_text(encoding="utf-8")

    assert "TrajectoryResponse" in text
    assert "/observability/tasks/${taskId}/trajectory" in text


def test_observability_trajectory_styles_exist() -> None:
    text = GLOBAL_CSS.read_text(encoding="utf-8")

    assert ".trajectory-panel" in text
    assert ".trajectory-summary" in text
    assert ".trajectory-step" in text
    assert ".trajectory-index.success" in text
