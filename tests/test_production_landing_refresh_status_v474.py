from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_refresh_status import build_production_landing_refresh_status


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _summary(step: str, status: str = "partial") -> dict:
    return {
        "status": status,
        "generated_at": f"2026-06-05T00:00:0{len(step) % 9}+00:00",
        "json_path": f"docs/reports/{step}/latest.json",
        "markdown_path": f"docs/reports/{step}/latest.md",
        "secret_plaintext_output": False,
    }


def test_production_landing_refresh_status_runs_steps_in_dependency_order(tmp_path: Path) -> None:
    calls: list[str] = []
    final_payload_path = tmp_path / "final_status.json"
    final_payload_path.write_text(
        json.dumps(
            {
                "status": "partial",
                "blockers": ["manual_signoff:not_completed", "pilot_signoff:real_infra_not_ready"],
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def builder(name: str, status: str = "partial"):
        def run(**_kwargs):
            calls.append(name)
            if name == "production_landing_status":
                return {
                    "status": "partial",
                    "generated_at": "2026-06-05T00:00:09+00:00",
                    "json_path": str(final_payload_path),
                    "markdown_path": str(tmp_path / "final_status.md"),
                    "secret_plaintext_output": False,
                }
            if name == "production_landing_final_verification":
                return _summary(name, status="partial")
            return _summary(name, status=status)

        return run

    summary = build_production_landing_refresh_status(
        output_dir=tmp_path / "out",
        closure_evidence=tmp_path / "closure.json",
        builders={
            "execution_gate": builder("execution_gate"),
            "real_integration_staging_gate": builder("real_integration_staging_gate"),
            "real_integration_gap_register": builder("real_integration_gap_register"),
            "real_production_environment_checklist": builder("real_production_environment_checklist"),
            "production_landing_input_readiness": builder("production_landing_input_readiness"),
            "manual_signoff_evidence_ack_status": builder("manual_signoff_evidence_ack_status"),
            "manual_signoff_record_validation": builder("manual_signoff_record_validation"),
            "manual_signoff_record_promote": builder("manual_signoff_record_promote"),
            "production_landing_text_quality": builder("production_landing_text_quality", "success"),
            "operations_console_landing_smoke": builder("operations_console_landing_smoke", "skipped"),
            "production_pilot_signoff": builder("production_pilot_signoff"),
            "production_landing_action_pack": builder("production_landing_action_pack"),
            "production_landing_blocker_resolution": builder("production_landing_blocker_resolution"),
            "production_landing_status": builder("production_landing_status"),
            "production_landing_final_verification": builder("production_landing_final_verification"),
        },
    )
    payload = _read_payload(summary)

    assert calls == [
        "execution_gate",
        "real_integration_staging_gate",
        "real_integration_gap_register",
        "real_production_environment_checklist",
        "production_pilot_signoff",
        "production_landing_input_readiness",
        "manual_signoff_evidence_ack_status",
        "manual_signoff_record_validation",
        "manual_signoff_record_promote",
        "production_landing_text_quality",
        "operations_console_landing_smoke",
        "production_landing_action_pack",
        "production_landing_blocker_resolution",
        "production_landing_status",
        "production_landing_final_verification",
    ]
    assert summary["status"] == "partial"
    assert payload["final_status"] == "partial"
    assert payload["blocker_count"] == 2
    assert payload["final_blockers"] == ["manual_signoff:not_completed", "pilot_signoff:real_infra_not_ready"]
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["business_data_written"] is False


def test_production_landing_refresh_status_marks_blocked_when_a_step_blocks(tmp_path: Path) -> None:
    final_payload_path = tmp_path / "final_status.json"
    final_payload_path.write_text(
        json.dumps({"status": "partial", "blockers": ["source_status:blocked_or_failed"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    def final_status(**_kwargs):
        return {
            "status": "partial",
            "json_path": str(final_payload_path),
            "markdown_path": str(tmp_path / "final_status.md"),
            "secret_plaintext_output": False,
        }

    summary = build_production_landing_refresh_status(
        output_dir=tmp_path / "out",
        builders={
            "execution_gate": lambda **_kwargs: _summary("execution_gate"),
            "real_integration_staging_gate": lambda **_kwargs: _summary("real_integration_staging_gate"),
            "real_integration_gap_register": lambda **_kwargs: _summary("real_integration_gap_register", "blocked"),
            "real_production_environment_checklist": lambda **_kwargs: _summary("real_production_environment_checklist"),
            "production_landing_input_readiness": lambda **_kwargs: _summary("production_landing_input_readiness"),
            "manual_signoff_evidence_ack_status": lambda **_kwargs: _summary("manual_signoff_evidence_ack_status"),
            "manual_signoff_record_validation": lambda **_kwargs: _summary("manual_signoff_record_validation"),
            "manual_signoff_record_promote": lambda **_kwargs: _summary("manual_signoff_record_promote"),
            "production_landing_text_quality": lambda **_kwargs: _summary("production_landing_text_quality"),
            "operations_console_landing_smoke": lambda **_kwargs: _summary("operations_console_landing_smoke", "skipped"),
            "production_pilot_signoff": lambda **_kwargs: _summary("production_pilot_signoff"),
            "production_landing_action_pack": lambda **_kwargs: _summary("production_landing_action_pack"),
            "production_landing_blocker_resolution": lambda **_kwargs: _summary("production_landing_blocker_resolution"),
            "production_landing_status": final_status,
            "production_landing_final_verification": lambda **_kwargs: _summary("production_landing_final_verification"),
        },
    )
    payload = _read_payload(summary)

    assert summary["status"] == "blocked"
    assert payload["blocked_steps"] == ["real_integration_gap_register"]
    assert payload["final_status"] == "partial"
    assert payload["secret_plaintext_output"] is False
