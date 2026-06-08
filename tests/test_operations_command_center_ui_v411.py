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
    assert "controlled_pilot_run_packet: \"run packet\"" in text
    assert "\"Manual-Review\": \"Manual Review\"" in text


def test_operations_page_prefers_run_packet_for_controlled_pilot_decision() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    run_packet_index = text.index("controlled_pilot_run_packet?.controlled_internal_pilot")
    status_summary_index = text.index("controlled_pilot_status_summary?.controlled_internal_pilot")

    assert run_packet_index < status_summary_index


def test_operations_page_prefers_backend_landing_command_center_contract() -> None:
    text = OPERATIONS_PAGE.read_text(encoding="utf-8")

    command_center_index = text.index("landing_command_center")
    run_packet_index = text.index("controlled_pilot_run_packet?.controlled_internal_pilot")

    assert command_center_index < run_packet_index
    assert "landingCommandCenter" in text


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
