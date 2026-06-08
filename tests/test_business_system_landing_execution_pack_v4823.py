from __future__ import annotations

import json
from pathlib import Path

from scripts.business_system_landing_execution_pack import build_business_system_landing_execution_pack


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _dirs(root: Path) -> dict[str, Path]:
    return {
        "business_system_input_packet": root / "input",
        "business_system_production_readiness": root / "readiness",
        "business_system_read_smoke": root / "smoke",
    }


def _base_reports(root: Path) -> dict[str, Path]:
    dirs = _dirs(root)
    _write_json(
        dirs["business_system_input_packet"] / "001_business_system_input_packet.json",
        {
            "generated_at": "2026-06-06T00:00:00+00:00",
            "status": "needs_input",
            "ready_for_real_read_smoke": False,
            "owner_inputs_present": {
                "business_owner": False,
                "security_reviewer": False,
                "operations_owner": False,
                "data_owner": False,
            },
            "missing_conditions": [
                "owner:business_owner_missing",
                "env_target:BUSINESS_SYSTEM_BASE_URL_missing",
            ],
            "missing_condition_count": 2,
            "manual_input_checklist": [
                {
                    "id": "owners",
                    "env": ["BUSINESS_SYSTEM_BUSINESS_OWNER"],
                    "description": "填写负责人名称或工号，不填写 token。",
                }
            ],
            "recommended_commands": [
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv"
            ],
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "001_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-06T00:00:01+00:00",
            "status": "needs_input",
            "owner_inputs_present": {
                "business_owner": False,
                "security_reviewer": False,
                "operations_owner": False,
                "data_owner": False,
            },
            "missing_conditions": [
                "owner:business_owner_missing",
                "evidence:business_system_real_read_smoke_not_executed",
            ],
            "missing_condition_count": 2,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "001_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-06T00:00:02+00:00",
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "secret_plaintext_output": False,
            "missing_conditions": ["cli:--execute_not_requested"],
            "public_production_direct_launch": "No-Go",
        },
    )
    return dirs


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_business_system_landing_execution_pack_needs_input(tmp_path: Path) -> None:
    dirs = _base_reports(tmp_path / "sources")

    summary = build_business_system_landing_execution_pack(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert summary["ready_for_real_read_smoke"] is False
    assert summary["real_read_smoke_complete"] is False
    assert summary["safe_next_action"] == "complete_business_system_inputs"
    assert payload["missing_by_category"]["owners"] == ["owner:business_owner_missing"]
    assert "env_target:BUSINESS_SYSTEM_BASE_URL_missing" in payload["missing_by_category"]["environment"]
    assert "evidence:business_system_real_read_smoke_not_executed" in payload["missing_by_category"]["evidence"]
    assert payload["recommended_next_command"].endswith("scripts\\business_system_read_smoke.ps1 -UseExistingEnv")
    assert any(
        command.endswith(
            "scripts\\business_system_landing_resume.ps1 -UseExistingEnv -EnvPath local\\production_landing.staging.env"
        )
        for command in payload["recommended_commands"]
    )
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False


def test_business_system_landing_execution_pack_ready_for_real_read_smoke(tmp_path: Path) -> None:
    dirs = _base_reports(tmp_path / "sources")
    _write_json(
        dirs["business_system_input_packet"] / "002_business_system_input_packet.json",
        {
            "generated_at": "2026-06-06T00:30:00+00:00",
            "status": "ready",
            "ready_for_real_read_smoke": True,
            "owner_inputs_present": {
                "business_owner": True,
                "security_reviewer": True,
                "operations_owner": True,
                "data_owner": True,
            },
            "missing_conditions": [],
            "missing_condition_count": 0,
            "manual_input_checklist": [],
            "recommended_commands": [
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv"
            ],
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_business_system_landing_execution_pack(output_dir=tmp_path / "out", report_dirs=dirs)

    assert summary["status"] == "needs_input"
    assert summary["ready_for_real_read_smoke"] is True
    assert summary["real_read_smoke_complete"] is False
    assert summary["safe_next_action"] == "execute_real_read_smoke"
    payload = _payload(summary)
    assert payload["recommended_next_command"].endswith(
        "scripts\\business_system_read_smoke.ps1 -UseExistingEnv"
    )
    assert "BusinessOwner WYJ" not in payload["recommended_next_command"]
    assert any(
        command.endswith(
            "scripts\\business_system_landing_resume.ps1 -UseExistingEnv -EnvPath local\\production_landing.staging.env"
        )
        for command in payload["recommended_commands"]
    )


def test_business_system_landing_execution_pack_prioritizes_real_smoke_over_preflight(
    tmp_path: Path,
) -> None:
    dirs = _base_reports(tmp_path / "sources")
    _write_json(
        dirs["business_system_input_packet"] / "002_business_system_input_packet.json",
        {
            "generated_at": "2026-06-06T00:30:00+00:00",
            "status": "ready",
            "ready_for_real_read_smoke": True,
            "owner_inputs_present": {
                "business_owner": True,
                "security_reviewer": True,
                "operations_owner": True,
                "data_owner": True,
            },
            "missing_conditions": [],
            "missing_condition_count": 0,
            "recommended_commands": [
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -PreflightOnly -EnvPath local\\production_landing.staging.env",
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv",
            ],
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_business_system_landing_execution_pack(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = _payload(summary)

    assert summary["safe_next_action"] == "execute_real_read_smoke"
    assert "-PreflightOnly" not in payload["recommended_next_command"]
    assert payload["recommended_next_command"].endswith(
        "scripts\\business_system_read_smoke.ps1 -UseExistingEnv"
    )
    assert "BusinessOwner WYJ" not in payload["recommended_next_command"]


def test_business_system_landing_execution_pack_ready_after_real_read_smoke(tmp_path: Path) -> None:
    dirs = _base_reports(tmp_path / "sources")
    _write_json(
        dirs["business_system_input_packet"] / "002_business_system_input_packet.json",
        {
            "generated_at": "2026-06-06T00:30:00+00:00",
            "status": "ready",
            "ready_for_real_read_smoke": True,
            "owner_inputs_present": {
                "business_owner": True,
                "security_reviewer": True,
                "operations_owner": True,
                "data_owner": True,
            },
            "missing_conditions": [],
            "missing_condition_count": 0,
            "recommended_commands": [],
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "002_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-06T00:30:01+00:00",
            "status": "ready",
            "missing_conditions": [],
            "missing_condition_count": 0,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "002_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-06T00:30:02+00:00",
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "secret_plaintext_output": False,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_business_system_landing_execution_pack(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "ready"
    assert summary["safe_next_action"] == "refresh_controlled_pilot_gate"
    assert payload["missing_condition_count"] == 0
    assert payload["business_system_read_smoke"]["business_read_executed"] is True
    assert payload["recommended_next_command"].endswith(
        "scripts\\business_system_landing_resume.ps1 -UseExistingEnv -EnvPath local\\production_landing.staging.env"
    )
    assert any(
        command.endswith(
            "scripts\\business_system_landing_resume.ps1 -UseExistingEnv -EnvPath local\\production_landing.staging.env"
        )
        for command in payload["recommended_commands"]
    )


def test_business_system_landing_execution_pack_binds_explicit_current_reports_over_stale_success(
    tmp_path: Path,
) -> None:
    dirs = _base_reports(tmp_path / "sources")
    current_input = _write_json(
        dirs["business_system_input_packet"] / "010_current_business_system_input_packet.json",
        {
            "generated_at": "2026-06-06T00:10:00+00:00",
            "status": "ready",
            "ready_for_real_read_smoke": True,
            "owner_inputs_present": {
                "business_owner": True,
                "security_reviewer": True,
                "operations_owner": True,
                "data_owner": True,
            },
            "missing_conditions": [],
            "missing_condition_count": 0,
            "recommended_commands": [
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv"
            ],
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    current_readiness = _write_json(
        dirs["business_system_production_readiness"] / "010_current_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-06T00:10:01+00:00",
            "status": "needs_input",
            "missing_conditions": ["evidence:business_system_real_read_smoke_not_executed"],
            "missing_condition_count": 1,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    current_smoke = _write_json(
        dirs["business_system_read_smoke"] / "010_current_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-06T00:10:02+00:00",
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "secret_plaintext_output": False,
            "missing_conditions": ["cli:--execute_not_requested"],
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["business_system_input_packet"] / "999_stale_business_system_input_packet.json",
        {
            "generated_at": "2026-06-06T01:00:00+00:00",
            "status": "ready",
            "ready_for_real_read_smoke": True,
            "missing_conditions": [],
            "missing_condition_count": 0,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "999_stale_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-06T01:00:01+00:00",
            "status": "ready",
            "missing_conditions": [],
            "missing_condition_count": 0,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "999_stale_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-06T01:00:02+00:00",
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "secret_plaintext_output": False,
            "missing_conditions": [],
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_business_system_landing_execution_pack(
        output_dir=tmp_path / "out",
        report_dirs=dirs,
        source_json_paths={
            "business_system_input_packet": current_input,
            "business_system_production_readiness": current_readiness,
            "business_system_read_smoke": current_smoke,
        },
    )
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert payload["source_bound"] is True
    assert payload["real_read_smoke_complete"] is False
    assert payload["business_system_read_smoke"]["business_read_executed"] is False
    assert payload["evidence_paths"]["business_system_input_packet"] == str(current_input.resolve())
    assert payload["evidence_paths"]["business_system_production_readiness"] == str(current_readiness.resolve())
    assert payload["evidence_paths"]["business_system_read_smoke"] == str(current_smoke.resolve())
    assert all(item["source_bound"] is True for item in payload["sources"].values())
    assert all(item["source_selection"] == "explicit_json_path" for item in payload["sources"].values())
    assert "evidence:business_system_real_read_smoke_not_executed" in payload["missing_conditions"]


def test_business_system_landing_execution_pack_uses_readiness_missing_over_stale_smoke_env_gaps(
    tmp_path: Path,
) -> None:
    dirs = _dirs(tmp_path / "reports")
    _write_json(
        dirs["business_system_input_packet"] / "001_business_system_input_packet.json",
        {
            "status": "needs_input",
            "ready_for_real_read_smoke": False,
            "missing_conditions": ["env_target:BUSINESS_SYSTEM_BASE_URL_missing"],
            "owner_inputs_present": {
                "business_owner": True,
                "security_reviewer": True,
                "operations_owner": True,
                "data_owner": True,
            },
        },
    )
    _write_json(
        dirs["business_system_production_readiness"] / "001_business_system_production_readiness.json",
        {
            "status": "needs_input",
            "missing_conditions": [
                "env_target:BUSINESS_SYSTEM_BASE_URL_ENV_missing",
                "env_target:BUSINESS_SYSTEM_TOKEN_ENV_missing",
                "evidence:business_system_real_read_smoke_not_executed",
            ],
            "owner_inputs_present": {
                "business_owner": True,
                "security_reviewer": True,
                "operations_owner": True,
                "data_owner": True,
            },
        },
    )
    _write_json(
        dirs["business_system_read_smoke"] / "001_business_system_read_smoke.json",
        {
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "secret_plaintext_output": False,
            "missing_conditions": [
                "cli:--execute_not_requested",
                "owner:business_owner_missing",
                "opt_in:BUSINESS_INTEGRATION_ENABLED_not_enabled",
                "env:BUSINESS_SYSTEM_TOOL_ALLOWLIST_missing_business_read_probe",
            ],
        },
    )

    summary = build_business_system_landing_execution_pack(output_dir=tmp_path / "out", report_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert "evidence:business_system_real_read_smoke_not_executed" in payload["missing_conditions"]
    assert "owner:business_owner_missing" not in payload["missing_conditions"]
    assert "opt_in:BUSINESS_INTEGRATION_ENABLED_not_enabled" not in payload["missing_conditions"]
    assert "env:BUSINESS_SYSTEM_TOOL_ALLOWLIST_missing_business_read_probe" not in payload["missing_conditions"]


def test_business_system_landing_execution_pack_blocks_missing_explicit_source_without_latest_fallback(
    tmp_path: Path,
) -> None:
    dirs = _base_reports(tmp_path / "sources")
    _write_json(
        dirs["business_system_input_packet"] / "999_business_system_input_packet.json",
        {
            "generated_at": "2026-06-06T01:00:00+00:00",
            "status": "ready",
            "ready_for_real_read_smoke": True,
            "missing_conditions": [],
            "missing_condition_count": 0,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    missing_path = dirs["business_system_input_packet"] / "missing_business_system_input_packet.json"

    summary = build_business_system_landing_execution_pack(
        output_dir=tmp_path / "out",
        report_dirs=dirs,
        source_json_paths={"business_system_input_packet": missing_path},
    )
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert payload["sources"]["business_system_input_packet"]["source_selection"] == "explicit_json_path"
    assert payload["sources"]["business_system_input_packet"]["source_bound"] is False
    assert payload["evidence_paths"]["business_system_input_packet"] == str(missing_path)
    assert "business_system_input_packet:explicit_json_path_missing" in payload["missing_conditions"]


def test_business_system_landing_execution_pack_blocks_secret_or_write_evidence(tmp_path: Path) -> None:
    dirs = _base_reports(tmp_path / "sources")
    _write_json(
        dirs["business_system_read_smoke"] / "002_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-06T00:30:02+00:00",
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": True,
            "business_data_written": True,
            "local_business_mock_used": False,
            "secret_plaintext_output": True,
            "missing_conditions": ["boundary:business_write_detected", "boundary:secret_plaintext_output_detected"],
            "note": "token=sk-should-not-leak",
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_business_system_landing_execution_pack(output_dir=tmp_path / "out", report_dirs=dirs)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["secret_plaintext_output"] is True
    assert "sk-should-not-leak" not in merged
    payload = _payload(summary)
    assert payload["secret_plaintext_output"] is True
    assert "boundary:secret_like_text_detected" in payload["missing_conditions"]
