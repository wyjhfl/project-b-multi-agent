from __future__ import annotations

import json
from pathlib import Path

from scripts.controlled_pilot_delivery_gate import build_controlled_pilot_delivery_gate


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_controlled_pilot_delivery_gate_allows_demo_business_only_gap(tmp_path: Path) -> None:
    status_path = _write_json(
        tmp_path / "status" / "001_production_landing_status.json",
        {
            "generated_at": "2026-06-08T00:00:00+00:00",
            "status": "partial",
            "controlled_pilot_ready": False,
            "ready_domain_count": 5,
            "domain_count": 5,
            "execution_allowed": True,
            "real_llm": {
                "status": "success",
                "real_llm_executed": True,
                "network_check_executed": True,
                "api_key_present": True,
            },
            "business_system": {
                "status": "success",
                "connected": True,
                "read_executed": True,
                "write_executed": False,
                "business_data_written": False,
                "local_mock_used": False,
                "demo_system_used": True,
                "real_system_connected": False,
                "real_read_smoke_required_for_public_production": True,
                "real_read_smoke_gap": True,
                "production_readiness_status": "needs_input",
                "landing_execution_pack_status": "needs_input",
            },
            "manual_signoff": {"completed": True, "record_present": True, "decision": "Go"},
            "blockers": ["business_system:real_business_system_required"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    final_path = _write_json(
        tmp_path / "final" / "001_production_landing_final_verification.json",
        {
            "generated_at": "2026-06-08T00:00:01+00:00",
            "status": "partial",
            "passed_count": 6,
            "requirement_count": 10,
            "missing_conditions": ["business_landing_execution_pack:not_ready"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_delivery_gate(
        output_dir=tmp_path / "out",
        status_report=status_path,
        final_verification_report=final_path,
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["controlled_pilot_delivery_ready"] is True
    assert payload["enterprise_landing_scope"] == "controlled_internal_pilot"
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["accepted_remaining_gaps"] == ["business_system:real_business_system_required"]
    assert payload["business_system"]["demo_system_used"] is True
    assert payload["business_system"]["real_system_connected"] is False
    assert payload["business_system"]["write_executed"] is False
    assert payload["business_system"]["business_data_written"] is False
    assert payload["secret_plaintext_output"] is False


def test_controlled_pilot_delivery_gate_blocks_business_write_or_extra_blockers(tmp_path: Path) -> None:
    status_path = _write_json(
        tmp_path / "status" / "001_production_landing_status.json",
        {
            "generated_at": "2026-06-08T00:00:00+00:00",
            "status": "partial",
            "ready_domain_count": 5,
            "domain_count": 5,
            "execution_allowed": True,
            "real_llm": {
                "status": "success",
                "real_llm_executed": True,
                "network_check_executed": True,
                "api_key_present": True,
            },
            "business_system": {
                "status": "success",
                "connected": True,
                "read_executed": True,
                "write_executed": True,
                "business_data_written": True,
                "demo_system_used": True,
                "real_system_connected": False,
            },
            "manual_signoff": {"completed": True, "record_present": True, "decision": "Go"},
            "blockers": ["business_system:real_business_system_required", "manual_signoff:not_completed"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )

    summary = build_controlled_pilot_delivery_gate(output_dir=tmp_path / "out", status_report=status_path)
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert payload["controlled_pilot_delivery_ready"] is False
    assert "business_system:write_or_data_mutation_detected" in payload["missing_conditions"]
    assert "blocker:manual_signoff:not_completed" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"
