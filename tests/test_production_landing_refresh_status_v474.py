from __future__ import annotations

import json
import os
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
            "business_system_read_smoke": builder("business_system_read_smoke"),
            "business_system_input_packet": builder("business_system_input_packet"),
            "business_system_production_readiness": builder("business_system_production_readiness"),
            "business_system_landing_execution_pack": builder("business_system_landing_execution_pack"),
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
        "business_system_read_smoke",
        "business_system_input_packet",
        "business_system_production_readiness",
        "business_system_landing_execution_pack",
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
            "business_system_read_smoke": lambda **_kwargs: _summary("business_system_read_smoke"),
            "business_system_input_packet": lambda **_kwargs: _summary("business_system_input_packet"),
            "business_system_production_readiness": lambda **_kwargs: _summary("business_system_production_readiness"),
            "business_system_landing_execution_pack": lambda **_kwargs: _summary("business_system_landing_execution_pack"),
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


def test_production_landing_refresh_status_loads_env_path_for_business_steps_and_restores_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    final_payload_path = tmp_path / "final_status.json"
    final_payload_path.write_text(
        json.dumps({"status": "partial", "blockers": ["business_landing_execution_pack:not_ready"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    env_path = tmp_path / "landing.env"
    env_path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=wyj",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BUSINESS_SYSTEM_BUSINESS_OWNER", "previous-owner")
    monkeypatch.delenv("BUSINESS_INTEGRATION_ENABLED", raising=False)
    observed: dict[str, object] = {}

    def business_input(**_kwargs):
        observed["input_enabled"] = os.getenv("BUSINESS_INTEGRATION_ENABLED")
        observed["input_owner"] = os.getenv("BUSINESS_SYSTEM_BUSINESS_OWNER")
        return {
            "status": "needs_input",
            "json_path": str(tmp_path / "input.json"),
            "markdown_path": str(tmp_path / "input.md"),
            "secret_plaintext_output": False,
        }

    def business_smoke(**_kwargs):
        observed["smoke_enabled"] = os.getenv("BUSINESS_INTEGRATION_ENABLED")
        observed["smoke_owner"] = os.getenv("BUSINESS_SYSTEM_BUSINESS_OWNER")
        return {
            "status": "skipped",
            "json_path": str(tmp_path / "smoke.json"),
            "markdown_path": str(tmp_path / "smoke.md"),
            "secret_plaintext_output": False,
        }

    def business_readiness(**kwargs):
        observed["readiness_enabled"] = os.getenv("BUSINESS_INTEGRATION_ENABLED")
        observed["readiness_owner"] = os.getenv("BUSINESS_SYSTEM_BUSINESS_OWNER")
        observed["readiness_smoke_json_path"] = kwargs.get("business_smoke_json_path")
        return {
            "status": "needs_input",
            "json_path": str(tmp_path / "readiness.json"),
            "markdown_path": str(tmp_path / "readiness.md"),
            "secret_plaintext_output": False,
        }

    def business_pack(**kwargs):
        observed["pack_enabled"] = os.getenv("BUSINESS_INTEGRATION_ENABLED")
        observed["pack_owner"] = os.getenv("BUSINESS_SYSTEM_BUSINESS_OWNER")
        observed["pack_source_json_paths"] = kwargs.get("source_json_paths")
        return _summary("business_system_landing_execution_pack")

    summary = build_production_landing_refresh_status(
        output_dir=tmp_path / "out",
        env_path=env_path,
        builders={
            "execution_gate": lambda **_kwargs: _summary("execution_gate"),
            "real_integration_staging_gate": lambda **_kwargs: _summary("real_integration_staging_gate"),
            "real_integration_gap_register": lambda **_kwargs: _summary("real_integration_gap_register"),
            "real_production_environment_checklist": lambda **_kwargs: _summary("real_production_environment_checklist"),
            "business_system_read_smoke": business_smoke,
            "business_system_input_packet": business_input,
            "business_system_production_readiness": business_readiness,
            "business_system_landing_execution_pack": business_pack,
            "production_landing_input_readiness": lambda **_kwargs: _summary("production_landing_input_readiness"),
            "manual_signoff_evidence_ack_status": lambda **_kwargs: _summary("manual_signoff_evidence_ack_status"),
            "manual_signoff_record_validation": lambda **_kwargs: _summary("manual_signoff_record_validation"),
            "manual_signoff_record_promote": lambda **_kwargs: _summary("manual_signoff_record_promote"),
            "production_landing_text_quality": lambda **_kwargs: _summary("production_landing_text_quality"),
            "operations_console_landing_smoke": lambda **_kwargs: _summary("operations_console_landing_smoke", "skipped"),
            "production_pilot_signoff": lambda **_kwargs: _summary("production_pilot_signoff"),
            "production_landing_action_pack": lambda **_kwargs: _summary("production_landing_action_pack"),
            "production_landing_blocker_resolution": lambda **_kwargs: _summary("production_landing_blocker_resolution"),
            "production_landing_status": lambda **_kwargs: {
                "status": "partial",
                "json_path": str(final_payload_path),
                "markdown_path": str(tmp_path / "final_status.md"),
                "secret_plaintext_output": False,
            },
            "production_landing_final_verification": lambda **_kwargs: _summary("production_landing_final_verification"),
        },
    )
    payload = _read_payload(summary)

    assert observed["input_enabled"] == "true"
    assert observed["input_owner"] == "wyj"
    assert observed["smoke_enabled"] == "true"
    assert observed["smoke_owner"] == "wyj"
    assert observed["readiness_enabled"] == "true"
    assert observed["readiness_owner"] == "wyj"
    assert observed["readiness_smoke_json_path"] == str(tmp_path / "smoke.json")
    assert observed["pack_enabled"] == "true"
    assert observed["pack_owner"] == "wyj"
    assert observed["pack_source_json_paths"] == {
        "business_system_input_packet": str(tmp_path / "input.json"),
        "business_system_production_readiness": str(tmp_path / "readiness.json"),
        "business_system_read_smoke": str(tmp_path / "smoke.json"),
    }
    assert os.getenv("BUSINESS_INTEGRATION_ENABLED") is None
    assert os.getenv("BUSINESS_SYSTEM_BUSINESS_OWNER") == "previous-owner"
    assert payload["public_production_direct_launch"] == "No-Go"
