from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_pre_signoff_gate import build_production_landing_pre_signoff_gate


def _write_report(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sources(root: Path) -> dict[str, tuple[Path, str]]:
    return {
        "production_landing_status": (root / "status", "*.json"),
        "production_landing_final_verification": (root / "final", "*.json"),
        "production_landing_action_pack": (root / "action", "*.json"),
        "manual_signoff_evidence_ack_status": (root / "ack", "*.json"),
        "production_landing_signoff_closeout": (root / "closeout", "*.json"),
    }


def test_pre_signoff_gate_ready_when_only_manual_signoff_remains(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_report(
        root / "status",
        "001.json",
        {"status": "partial", "blockers": ["action_pack:required_inputs_remaining", "manual_signoff:not_completed"]},
    )
    _write_report(
        root / "final",
        "001.json",
        {
            "status": "partial",
            "missing_conditions": [
                "blocker:action_pack:required_inputs_remaining",
                "blocker:manual_signoff:not_completed",
                "manual_signoff:not_completed",
                "production_landing_status:not_ready",
                "production_landing_status:status_not_success",
                "refresh_status:final_status_not_success",
                "refresh_status:status_not_success",
            ],
        },
    )
    _write_report(root / "action", "001.json", {"status": "partial", "required_input_count": 1})
    _write_report(
        root / "ack",
        "001.json",
        {"status": "success", "recommended_accept_count": 4, "item_count": 4, "secret_plaintext_output": False},
    )
    _write_report(
        root / "closeout",
        "001.json",
        {
            "status": "partial",
            "missing_conditions": [
                "production_landing_signoff_closeout:confirm_controlled_pilot_go_required",
                "production_landing_signoff_closeout:confirm_manual_signoff_required",
            ],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_pre_signoff_gate(output_dir=tmp_path / "out", sources=_sources(root))
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "ready_for_manual_signoff"
    assert summary["ready_for_manual_signoff"] is True
    assert payload["technical_evidence_ready"] is True
    assert payload["non_signoff_blocker_count"] == 0
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False


def test_pre_signoff_gate_partial_when_technical_blocker_remains(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_report(root / "status", "001.json", {"status": "partial", "blockers": ["real_llm_preflight:not_success"]})
    _write_report(root / "final", "001.json", {"status": "partial", "missing_conditions": ["real_llm_preflight:not_success"]})
    _write_report(root / "action", "001.json", {"status": "partial", "required_input_count": 2})
    _write_report(root / "ack", "001.json", {"status": "partial", "recommended_accept_count": 3, "item_count": 4})
    _write_report(root / "closeout", "001.json", {"status": "partial", "missing_conditions": []})

    summary = build_production_landing_pre_signoff_gate(output_dir=tmp_path / "out", sources=_sources(root))
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert summary["status"] == "partial"
    assert summary["ready_for_manual_signoff"] is False
    assert payload["non_signoff_blocker_count"] >= 1
    assert "real_llm_preflight:not_success" in payload["non_signoff_blockers"]


def test_pre_signoff_gate_blocks_secret_like_report_content_without_leaking_value(tmp_path: Path) -> None:
    root = tmp_path / "reports"
    _write_report(root / "status", "001.json", {"status": "partial", "blockers": []})
    _write_report(root / "final", "001.json", {"status": "partial", "missing_conditions": []})
    _write_report(root / "action", "001.json", {"status": "partial", "required_input_count": 1})
    _write_report(root / "ack", "001.json", {"status": "success", "recommended_accept_count": 4, "item_count": 4})
    _write_report(root / "closeout", "001.json", {"status": "partial", "note": "token=sk-should-not-leak"})

    summary = build_production_landing_pre_signoff_gate(output_dir=tmp_path / "out", sources=_sources(root))
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["ready_for_manual_signoff"] is False
    assert "sk-should-not-leak" not in merged
