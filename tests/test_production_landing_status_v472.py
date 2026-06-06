from __future__ import annotations

import json
from pathlib import Path

from scripts import production_landing_status as status_module
from scripts.production_landing_status import build_production_landing_status


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _patch_sources(monkeypatch, root: Path) -> dict[str, Path]:
    dirs = {
        "env_check": root / "env_check",
        "execution_gate": root / "execution_gate",
        "xiaomi_llm_preflight": root / "xiaomi_llm_preflight",
        "business_read_smoke": root / "business_read_smoke",
        "business_production_readiness": root / "business_production_readiness",
        "action_pack": root / "action_pack",
        "pilot_signoff": root / "pilot_signoff",
        "manual_signoff_record_validation": root / "manual_signoff_record_validation",
    }
    monkeypatch.setattr(
        status_module,
        "REPORT_SOURCES",
        {
            "env_check": {"dir": dirs["env_check"], "pattern": "*_production_landing_env_check.json"},
            "execution_gate": {"dir": dirs["execution_gate"], "pattern": "*_production_landing_execution_gate.json"},
            "xiaomi_llm_preflight": {
                "dir": dirs["xiaomi_llm_preflight"],
                "pattern": "*_production_landing_xiaomi_llm_preflight.json",
            },
            "business_read_smoke": {"dir": dirs["business_read_smoke"], "pattern": "*_business_system_read_smoke.json"},
            "business_production_readiness": {
                "dir": dirs["business_production_readiness"],
                "pattern": "*_business_system_production_readiness.json",
            },
            "action_pack": {"dir": dirs["action_pack"], "pattern": "*_production_landing_action_pack.json"},
            "pilot_signoff": {"dir": dirs["pilot_signoff"], "pattern": "*_production_pilot_signoff.json"},
            "manual_signoff_record_validation": {
                "dir": dirs["manual_signoff_record_validation"],
                "pattern": "*_manual_signoff_record_validation.json",
            },
        },
    )
    return dirs


def _write_ready_reports(dirs: dict[str, Path]) -> None:
    _write_json(
        dirs["env_check"] / "001_production_landing_env_check.json",
        {"status": "success", "ready_domain_count": 5, "domain_count": 5, "secret_plaintext_output": False},
    )
    _write_json(
        dirs["execution_gate"] / "001_production_landing_execution_gate.json",
        {
            "status": "success",
            "ready_domains": ["real_llm", "postgres", "redis", "external_mcp", "business_system"],
            "blocked_domains": [],
            "ready_domain_count": 5,
            "requested_domain_count": 5,
            "execution_allowed": True,
            "safe_runner_commands": ["python scripts/production_landing_env_runner.py --action staging-smoke"],
        },
    )
    _write_json(
        dirs["xiaomi_llm_preflight"] / "001_production_landing_xiaomi_llm_preflight.json",
        {
            "status": "success",
            "api_key_present": True,
            "real_llm_executed": True,
            "safe_next_action": "refresh_landing_status_and_continue_manual_signoff",
            "acceptance_blockers": [],
            "preflight": {
                "network_check_requested": True,
                "network_check_allowed": True,
                "network_check_executed": True,
            },
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_read_smoke"] / "001_business_system_read_smoke.json",
        {
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": True,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_production_readiness"] / "001_business_system_production_readiness.json",
        {
            "status": "ready",
            "missing_condition_count": 0,
            "missing_conditions": [],
            "latest_business_smoke": {
                "business_read_executed": True,
                "business_write_executed": False,
                "business_data_written": False,
                "local_business_mock_used": False,
            },
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["action_pack"] / "001_production_landing_action_pack.json",
        {"status": "success", "required_input_count": 0, "recommended_commands": [], "secret_plaintext_output": False},
    )
    _write_json(
        dirs["pilot_signoff"] / "001_production_pilot_signoff.json",
        {
            "status": "partial",
            "manual_signoff_completed": True,
            "manual_signoff_record_present": True,
            "manual_signoff_decision": "Go",
            "landing_status": {"real_infra_ready": True, "enterprise_landing_state": "controlled-pilot-manual-review"},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["manual_signoff_record_validation"] / "001_manual_signoff_record_validation.json",
        {
            "status": "success",
            "manual_signoff_completed": True,
            "signoff_record_present": True,
            "decision": "Go",
            "missing_condition_count": 0,
            "secret_plaintext_output": False,
        },
    )


def test_production_landing_status_reports_partial_with_current_blockers(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["execution_gate"] / "002_production_landing_execution_gate.json",
        {
            "status": "partial",
            "ready_domains": ["postgres", "redis", "external_mcp", "business_system"],
            "blocked_domains": ["real_llm"],
            "ready_domain_count": 4,
            "requested_domain_count": 5,
            "execution_allowed": False,
            "safe_runner_commands": [
                "python scripts/production_landing_env_runner.py --action env-check",
                "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1",
            ],
        },
    )
    _write_json(
        dirs["env_check"] / "002_production_landing_env_check.json",
        {"status": "partial", "ready_domain_count": 4, "domain_count": 5, "secret_plaintext_output": False},
    )
    _write_json(
        dirs["action_pack"] / "002_production_landing_action_pack.json",
        {
            "status": "partial",
            "required_input_count": 3,
            "required_inputs": [{"input_id": "manual_signoff_record", "status": "required"}],
            "recommended_commands": [],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert payload["ready_domains"] == ["postgres", "redis", "external_mcp", "business_system"]
    assert payload["blocked_domains"] == ["real_llm"]
    assert "execution_gate:not_allowed" in payload["blockers"]
    assert "env_check:not_all_domains_ready" in payload["blockers"]
    assert "action_pack:required_inputs_remaining" in payload["blockers"]
    assert payload["next_commands"][1] == "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1"
    assert payload["controlled_pilot_ready"] is False
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False
    assert payload["xiaomi_llm"]["network_check_requested"] is True
    assert payload["xiaomi_llm"]["network_check_allowed"] is True
    assert payload["xiaomi_llm"]["safe_next_action"] == "refresh_landing_status_and_continue_manual_signoff"


def test_production_landing_status_success_when_all_evidence_ready(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert summary["controlled_pilot_ready"] is True
    assert payload["blockers"] == []
    assert payload["ready_domain_count"] == 5
    assert payload["xiaomi_llm"]["real_llm_executed"] is True
    assert payload["business_system"]["read_executed"] is True
    assert payload["business_system"]["business_data_written"] is False
    assert payload["business_system"]["local_mock_used"] is True
    assert payload["business_system"]["real_system_connected"] is False
    assert payload["business_system"]["production_readiness_status"] == "ready"
    assert payload["business_system"]["production_readiness_missing_count"] == 0
    assert payload["business_system"]["production_readiness_public_production_gap"] is False
    assert payload["manual_signoff"]["completed"] is True


def test_production_landing_status_tracks_business_readiness_public_gap_without_blocking_controlled_pilot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["business_production_readiness"] / "002_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-06T00:00:01+00:00",
            "status": "needs_input",
            "missing_condition_count": 2,
            "missing_conditions": [
                "owner:operations_owner_missing",
                "evidence:business_system_real_read_smoke_not_executed",
            ],
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["controlled_pilot_ready"] is True
    assert payload["business_system"]["production_readiness_status"] == "needs_input"
    assert payload["business_system"]["production_readiness_missing_count"] == 2
    assert payload["business_system"]["production_readiness_public_production_gap"] is True
    assert payload["business_system"]["production_readiness_missing_conditions"] == [
        "owner:operations_owner_missing",
        "evidence:business_system_real_read_smoke_not_executed",
    ]
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_status_does_not_block_on_local_llm_placeholder_when_real_preflight_succeeded(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    blocked_domain = {
        "domain_id": "real_llm",
        "ready_for_execute": False,
        "blocker_reason": "placeholder_env",
        "placeholder_keys": ["XIAOMI_LLM_API_KEY"],
        "missing_keys": [],
    }
    _write_json(
        dirs["env_check"] / "002_production_landing_env_check.json",
        {
            "generated_at": "2026-06-05T07:00:00+00:00",
            "status": "partial",
            "ready_domain_count": 4,
            "domain_count": 5,
            "domains": [
                blocked_domain,
                {"domain_id": "postgres", "ready_for_execute": True},
                {"domain_id": "redis", "ready_for_execute": True},
                {"domain_id": "external_mcp", "ready_for_execute": True},
                {"domain_id": "business_system", "ready_for_execute": True},
            ],
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["execution_gate"] / "002_production_landing_execution_gate.json",
        {
            "generated_at": "2026-06-05T07:00:01+00:00",
            "status": "partial",
            "ready_domains": ["postgres", "redis", "external_mcp", "business_system"],
            "blocked_domains": ["real_llm"],
            "ready_domain_count": 4,
            "requested_domain_count": 5,
            "execution_allowed": False,
            "domains": [
                blocked_domain,
                {"domain_id": "postgres", "ready_for_execute": True},
                {"domain_id": "redis", "ready_for_execute": True},
                {"domain_id": "external_mcp", "ready_for_execute": True},
                {"domain_id": "business_system", "ready_for_execute": True},
            ],
            "safe_runner_commands": [],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["controlled_pilot_ready"] is True
    assert "env_check:not_all_domains_ready" not in payload["blockers"]
    assert "execution_gate:not_allowed" not in payload["blockers"]
    assert payload["blocked_domains"] == ["real_llm"]
    assert payload["xiaomi_llm"]["real_llm_executed"] is True


def test_production_landing_status_allows_env_check_evidence_override_with_strict_gate_llm_placeholder(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    blocked_domain = {
        "domain_id": "real_llm",
        "ready_for_execute": False,
        "blocker_reason": "placeholder_env",
        "placeholder_keys": ["XIAOMI_LLM_API_KEY"],
        "missing_keys": [],
    }
    _write_json(
        dirs["execution_gate"] / "002_production_landing_execution_gate.json",
        {
            "generated_at": "2026-06-05T07:05:01+00:00",
            "status": "partial",
            "ready_domains": ["postgres", "redis", "external_mcp", "business_system"],
            "blocked_domains": ["real_llm"],
            "ready_domain_count": 4,
            "requested_domain_count": 5,
            "execution_allowed": False,
            "domains": [
                blocked_domain,
                {"domain_id": "postgres", "ready_for_execute": True},
                {"domain_id": "redis", "ready_for_execute": True},
                {"domain_id": "external_mcp", "ready_for_execute": True},
                {"domain_id": "business_system", "ready_for_execute": True},
            ],
            "safe_runner_commands": [],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert payload["controlled_pilot_ready"] is True
    assert "execution_gate:not_allowed" not in payload["blockers"]
    assert payload["blocked_domains"] == ["real_llm"]


def test_production_landing_status_does_not_block_controlled_pilot_on_real_infra_gap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["pilot_signoff"] / "002_production_pilot_signoff.json",
        {
            "generated_at": "2026-06-05T06:00:00+00:00",
            "status": "skipped",
            "manual_signoff_completed": True,
            "manual_signoff_record_present": True,
            "manual_signoff_decision": "Go",
            "landing_status": {
                "real_infra_ready": False,
                "enterprise_landing_state": "needs-local-evidence",
                "production_blockers": ["real_infra:postgres_redis_mcp_not_all_connected"],
            },
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert "pilot_signoff:real_infra_not_ready" not in payload["blockers"]
    assert payload["controlled_pilot_ready"] is True
    assert payload["landing_state"] == "needs-local-evidence"
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_status_tracks_business_read_gap_as_public_production_gap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["business_read_smoke"] / "002_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-05T06:10:00+00:00",
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert "business_system_read:not_executed" not in payload["blockers"]
    assert payload["controlled_pilot_ready"] is True
    assert payload["business_system"]["real_read_smoke_gap"] is True
    assert payload["business_system"]["real_read_smoke_required_for_public_production"] is True
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_status_treats_business_credentials_input_as_non_blocking(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["action_pack"] / "002_production_landing_action_pack.json",
        {
            "generated_at": "2026-06-05T06:15:00+00:00",
            "status": "partial",
            "required_input_count": 1,
            "required_inputs": [
                {
                    "input_id": "business_system_read_only_credentials",
                    "status": "required",
                    "template": "docs/reports/business_system_read_smoke/business_read_smoke.env.template",
                }
            ],
            "recommended_commands": [],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert "action_pack:required_inputs_remaining" not in payload["blockers"]
    assert payload["required_input_count"] == 0
    assert payload["non_blocking_required_input_count"] == 1
    assert payload["controlled_pilot_ready"] is True


def test_production_landing_status_treats_real_infra_action_input_as_non_blocking(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["action_pack"] / "002_production_landing_action_pack.json",
        {
            "generated_at": "2026-06-05T06:20:00+00:00",
            "status": "partial",
            "required_input_count": 1,
            "required_inputs": [
                {
                    "input_id": "real_infra_current_round_acceptance",
                    "status": "required",
                    "required_env": ["DATABASE_URL=<secret-managed-url>"],
                }
            ],
            "recommended_commands": [],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert "action_pack:required_inputs_remaining" not in payload["blockers"]
    assert payload["required_input_count"] == 0
    assert payload["non_blocking_required_input_count"] == 1
    assert payload["public_production_direct_launch"] == "No-Go"


def test_production_landing_status_uses_validated_formal_manual_signoff_when_pilot_is_stale(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["pilot_signoff"] / "002_production_pilot_signoff.json",
        {
            "generated_at": "2026-06-05T06:00:00+00:00",
            "status": "partial",
            "manual_signoff_completed": False,
            "manual_signoff_record_present": False,
            "manual_signoff_decision": "",
            "landing_status": {"real_infra_ready": True, "enterprise_landing_state": "controlled-pilot-manual-review"},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["manual_signoff_record_validation"] / "002_manual_signoff_record_validation.json",
        {
            "generated_at": "2026-06-05T06:10:00+00:00",
            "status": "success",
            "manual_signoff_completed": True,
            "signoff_record_present": True,
            "decision": "Go",
            "missing_condition_count": 0,
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert "manual_signoff:not_completed" not in payload["blockers"]
    assert payload["manual_signoff"] == {"completed": True, "record_present": True, "decision": "Go"}


def test_production_landing_status_prefers_latest_generated_at_over_mtime(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["action_pack"] / "999_production_landing_action_pack.json",
        {
            "generated_at": "2026-06-04T20:00:00+00:00",
            "status": "success",
            "required_input_count": 0,
            "recommended_commands": [],
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["action_pack"] / "001_production_landing_action_pack.json",
        {
            "generated_at": "2026-06-04T20:30:00+00:00",
            "status": "partial",
            "required_input_count": 3,
            "required_inputs": [{"input_id": "manual_signoff_record", "status": "required"}],
            "recommended_commands": ["python scripts/production_landing_status.py"],
            "secret_plaintext_output": False,
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert payload["sources"]["action_pack"]["generated_at"] == "2026-06-04T20:30:00+00:00"
    assert "action_pack:required_inputs_remaining" in payload["blockers"]


def test_production_landing_status_blocks_secret_like_command_without_leak(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_sources(monkeypatch, tmp_path / "reports")
    _write_ready_reports(dirs)
    _write_json(
        dirs["execution_gate"] / "002_production_landing_execution_gate.json",
        {
            "status": "success",
            "ready_domains": ["real_llm", "postgres", "redis", "external_mcp", "business_system"],
            "blocked_domains": [],
            "ready_domain_count": 5,
            "requested_domain_count": 5,
            "execution_allowed": True,
            "safe_runner_commands": ["Authorization: Bearer should-not-leak"],
        },
    )

    summary = build_production_landing_status(output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert "landing_status:secret_like_output_detected" in payload["blockers"]
    assert "should-not-leak" not in merged
    assert "[redacted-secret-like-text]" in merged
