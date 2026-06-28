from __future__ import annotations

from pathlib import Path


OPERATIONS_PAGE = Path("frontend/src/app/operations/page.tsx")
GLOBAL_CSS = Path("frontend/src/app/globals.css")


def test_operations_page_exposes_landing_command_center_sections() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    assert "Landing Command Center" in text
    assert "landing-command-grid" in text
    assert "landing-decision-panel" in text
    assert "Evidence Chain" in text
    assert "Next Actions" in text
    assert "Controlled Pilot" in text
    assert "Public Launch" in text
    assert "Precommit Ready" in text
    assert "Action Pack" in text


def test_operations_page_humanizes_landing_decision_source_labels() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    assert "landingSourceLabel" in text
    assert "Gate source:" in text
    assert 'showcase_runtime_summary: "showcase runtime summary"' in text
    assert '"Manual-Review": "Manual Review"' in text


def test_operations_page_uses_backend_landing_command_center_contract() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    command_center_index = text.index("landing_command_center")
    derived_decision_index = text.index("landingCommandCenter?.controlled_internal_pilot")

    assert command_center_index < derived_decision_index
    assert "landingCommandCenter" in text
    assert "controlled_pilot_run_packet" not in text
    assert "controlled_pilot_status_summary" not in text


def test_operations_page_surfaces_landing_review_reasons_from_backend() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    assert "run_packet_missing_conditions" in text
    assert "landing-review-reasons" in text
    assert "Review Reasons" in text


def test_operations_page_surfaces_operator_guidance_commands() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    assert "operator_guidance" in text
    assert "Operator Guidance" in text
    assert "landing-guidance-list" in text
    assert "safe_boundary" in text


def test_operations_page_labels_current_showcase_actions() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    assert "start_local_demo" in text
    assert "run_demo_smoke" in text
    assert "inspect_multi_agent_trajectory" in text
    assert "run_text_quality_check" not in text


def test_operations_command_center_styles_are_responsive_and_non_marketing() -> None:
    text = GLOBAL_CSS.read_text(encoding="utf-8")

    assert ".landing-command-grid" in text
    assert ".landing-decision-panel" in text
    assert ".landing-evidence-grid" in text
    assert ".landing-next-actions" in text
    assert ".landing-review-reasons" in text
    assert ".landing-review-list" in text
    assert ".landing-guidance-list" in text
    assert "overflow-wrap: anywhere" in text
    assert "border-radius: 8px" in text
