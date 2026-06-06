from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_final_verification import build_production_landing_final_verification


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _ready_landing_status(**overrides: object) -> dict:
    payload = {
        "status": "success",
        "controlled_pilot_ready": True,
        "blockers": [],
        "xiaomi_llm": {
            "status": "success",
            "api_key_present": True,
            "network_check_executed": True,
            "real_llm_executed": True,
        },
        "business_system": {
            "status": "success",
            "connected": True,
            "read_executed": True,
            "write_executed": False,
            "business_data_written": False,
            "real_read_smoke_required_for_public_production": True,
            "real_read_smoke_gap": False,
            "production_readiness_status": "ready",
            "production_readiness_public_production_gap": False,
            "production_readiness_missing_count": 0,
        },
        "manual_signoff": {
            "completed": True,
            "record_present": True,
            "decision": "Go",
        },
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    payload.update(overrides)
    return payload


def _ready_refresh_status(**overrides: object) -> dict:
    payload = {
        "status": "success",
        "final_status": "success",
        "blocked_step_count": 0,
        "final_blockers": [],
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    payload.update(overrides)
    return payload


def _ready_operations_console_smoke(**overrides: object) -> dict:
    payload = {
        "status": "success",
        "execute": True,
        "checks": {
            "page_http_status": 200,
            "summary_http_status": 200,
            "backend_summary_http_status": 200,
            "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
            "acceptance_blockers": ["missing_process_env:XIAOMI_LLM_API_KEY"],
        },
        "missing_conditions": [],
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }
    payload.update(overrides)
    return payload


def test_production_landing_final_verification_reports_partial_for_open_blockers(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    refresh = tmp_path / "refresh.json"
    operations = tmp_path / "operations_console.json"
    _write_json(
        status,
        _ready_landing_status(
            status="partial",
            controlled_pilot_ready=False,
            blockers=["execution_gate:not_allowed"],
            xiaomi_llm={
                "status": "skipped",
                "api_key_present": False,
                "network_check_executed": False,
                "real_llm_executed": False,
            },
            manual_signoff={"completed": False, "record_present": True, "decision": "No-Go"},
        ),
    )
    _write_json(
        refresh,
        _ready_refresh_status(
            status="partial",
            final_status="partial",
            final_blockers=["execution_gate:not_allowed"],
        ),
    )
    _write_json(operations, _ready_operations_console_smoke())

    summary = build_production_landing_final_verification(
        output_dir=tmp_path / "out",
        status_report=status,
        refresh_report=refresh,
        operations_console_smoke_report=operations,
    )
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert payload["passed_count"] < payload["requirement_count"]
    assert "production_landing_status:status_not_success" in payload["missing_conditions"]
    assert "real_llm_preflight:not_success" in payload["missing_conditions"]
    assert "manual_signoff:not_completed" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False


def test_production_landing_final_verification_success_when_all_requirements_pass(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    refresh = tmp_path / "refresh.json"
    operations = tmp_path / "operations_console.json"
    _write_json(status, _ready_landing_status())
    _write_json(refresh, _ready_refresh_status())
    _write_json(operations, _ready_operations_console_smoke())

    summary = build_production_landing_final_verification(
        output_dir=tmp_path / "out",
        status_report=status,
        refresh_report=refresh,
        operations_console_smoke_report=operations,
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert summary["passed_count"] == summary["requirement_count"]
    assert payload["missing_conditions"] == []
    assert {item["passed"] for item in payload["requirements"]} == {True}
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_final_verification_allows_tracked_business_public_production_gap(
    tmp_path: Path,
) -> None:
    status = tmp_path / "status.json"
    refresh = tmp_path / "refresh.json"
    operations = tmp_path / "operations_console.json"
    _write_json(
        status,
        _ready_landing_status(
            business_system={
                "status": "skipped",
                "connected": False,
                "read_executed": False,
                "write_executed": False,
                "business_data_written": False,
                "real_read_smoke_required_for_public_production": True,
                "real_read_smoke_gap": True,
                "production_readiness_status": "needs_input",
                "production_readiness_public_production_gap": True,
                "production_readiness_missing_count": 2,
            }
        ),
    )
    _write_json(refresh, _ready_refresh_status())
    _write_json(operations, _ready_operations_console_smoke())

    summary = build_production_landing_final_verification(
        output_dir=tmp_path / "out",
        status_report=status,
        refresh_report=refresh,
        operations_console_smoke_report=operations,
    )
    payload = _payload(summary)
    business_requirement = next(
        item
        for item in payload["requirements"]
        if item["requirement_id"] == "business_read_only_public_production_gap_tracked"
    )

    assert summary["status"] == "success"
    assert business_requirement["passed"] is True
    assert business_requirement["evidence"]["real_read_smoke_gap"] is True
    assert business_requirement["evidence"]["production_readiness_public_production_gap"] is True
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_final_verification_requires_business_readiness_gap_tracking(
    tmp_path: Path,
) -> None:
    status = tmp_path / "status.json"
    refresh = tmp_path / "refresh.json"
    operations = tmp_path / "operations_console.json"
    business = _ready_landing_status()["business_system"]
    business.pop("production_readiness_status")
    business.pop("production_readiness_public_production_gap")
    _write_json(status, _ready_landing_status(business_system=business))
    _write_json(refresh, _ready_refresh_status())
    _write_json(operations, _ready_operations_console_smoke())

    summary = build_production_landing_final_verification(
        output_dir=tmp_path / "out",
        status_report=status,
        refresh_report=refresh,
        operations_console_smoke_report=operations,
    )
    payload = _payload(summary)
    business_requirement = next(
        item
        for item in payload["requirements"]
        if item["requirement_id"] == "business_read_only_public_production_gap_tracked"
    )

    assert summary["status"] == "partial"
    assert business_requirement["passed"] is False
    assert "business_read_only:public_production_gap_not_tracked" in payload["missing_conditions"]


def test_production_landing_final_verification_blocks_secret_like_output_without_leak(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    refresh = tmp_path / "refresh.json"
    operations = tmp_path / "operations_console.json"
    _write_json(status, _ready_landing_status(blockers=["token=sk-should-not-leak"]))
    _write_json(refresh, _ready_refresh_status())
    _write_json(operations, _ready_operations_console_smoke())

    summary = build_production_landing_final_verification(
        output_dir=tmp_path / "out",
        status_report=status,
        refresh_report=refresh,
        operations_console_smoke_report=operations,
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "final_verification:secret_like_output_detected" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in merged
    assert "[redacted-secret-like-text]" in merged


def test_production_landing_final_verification_requires_operations_console_smoke(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    refresh = tmp_path / "refresh.json"
    operations = tmp_path / "operations_console.json"
    _write_json(status, _ready_landing_status())
    _write_json(refresh, _ready_refresh_status())
    _write_json(operations, _ready_operations_console_smoke(status="skipped", execute=False))

    summary = build_production_landing_final_verification(
        output_dir=tmp_path / "out",
        status_report=status,
        refresh_report=refresh,
        operations_console_smoke_report=operations,
    )
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert "operations_console_landing_smoke:not_success" in payload["missing_conditions"]
    requirement = next(
        item for item in payload["requirements"] if item["requirement_id"] == "operations_console_landing_smoke_success"
    )
    assert requirement["passed"] is False
