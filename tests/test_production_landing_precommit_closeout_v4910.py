from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_precommit_closeout import build_production_landing_precommit_closeout


def _write_json(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_precommit_closeout_ready_when_only_freshness_waits_for_commit(tmp_path: Path) -> None:
    dirs = {
        "production_landing_action_pack": tmp_path / "action",
        "controlled_pilot_run_packet": tmp_path / "run_packet",
        "real_integration_staging_smoke": tmp_path / "infra",
        "production_landing_final_verification": tmp_path / "final",
        "production_landing_text_quality": tmp_path / "text_quality",
    }
    _write_json(
        dirs["production_landing_action_pack"],
        "001_production_landing_action_pack.json",
        {
            "generated_at": "2026-06-08T10:00:00+00:00",
            "status": "success",
            "required_input_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_run_packet"],
        "001_controlled_pilot_run_packet.json",
        {
            "generated_at": "2026-06-08T10:00:01+00:00",
            "status": "partial",
            "run_packet_ready": False,
            "controlled_internal_pilot": "Manual-Review",
            "missing_conditions": [
                "controlled_pilot_operator_packet:production_landing_evidence_freshness:not_fresh",
                "controlled_pilot_run_packet:required_ready_evidence_not_satisfied",
            ],
            "missing_condition_count": 2,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "real_production_remaining_gaps": ["business_system:real_business_system_required"],
        },
    )
    _write_json(
        dirs["real_integration_staging_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "generated_at": "2026-06-08T10:00:02+00:00",
            "status": "success",
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "real_llm_executed": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["production_landing_final_verification"],
        "001_production_landing_final_verification.json",
        {
            "generated_at": "2026-06-08T10:00:03+00:00",
            "status": "partial",
            "requirement_count": 10,
            "passed_count": 6,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["production_landing_text_quality"],
        "001_production_landing_text_quality.json",
        {
            "generated_at": "2026-06-08T10:00:04+00:00",
            "status": "success",
            "blocked_file_count": 0,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )

    summary = build_production_landing_precommit_closeout(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "ready"
    assert summary["precommit_landing_ready"] is True
    assert summary["public_production_direct_launch"] == "No-Go"
    assert payload["controlled_internal_pilot"] == "Manual-Review"
    assert payload["post_commit_required"] is True
    assert payload["accepted_precommit_missing_conditions"] == [
        "controlled_pilot_operator_packet:production_landing_evidence_freshness:not_fresh",
        "controlled_pilot_run_packet:required_ready_evidence_not_satisfied",
    ]
    assert payload["remaining_real_production_gaps"] == ["business_system:real_business_system_required"]
    assert payload["secret_plaintext_output"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False


def test_precommit_closeout_ready_when_run_packet_already_ready(tmp_path: Path) -> None:
    dirs = {
        "production_landing_action_pack": tmp_path / "action",
        "controlled_pilot_run_packet": tmp_path / "run_packet",
        "real_integration_staging_smoke": tmp_path / "infra",
        "production_landing_final_verification": tmp_path / "final",
        "production_landing_text_quality": tmp_path / "text_quality",
    }
    _write_json(
        dirs["production_landing_action_pack"],
        "001_production_landing_action_pack.json",
        {
            "status": "success",
            "required_input_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["controlled_pilot_run_packet"],
        "001_controlled_pilot_run_packet.json",
        {
            "status": "ready",
            "run_packet_ready": True,
            "controlled_internal_pilot": "Go",
            "missing_conditions": [],
            "missing_condition_count": 0,
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
            "real_production_remaining_gaps": ["business_system:real_business_system_required"],
        },
    )
    _write_json(
        dirs["real_integration_staging_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "status": "success",
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "real_llm_executed": False,
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "secret_plaintext_output": False,
            "public_production_direct_launch": "No-Go",
        },
    )
    _write_json(
        dirs["production_landing_final_verification"],
        "001_production_landing_final_verification.json",
        {"status": "partial", "secret_plaintext_output": False, "public_production_direct_launch": "No-Go"},
    )
    _write_json(
        dirs["production_landing_text_quality"],
        "001_production_landing_text_quality.json",
        {"status": "success", "blocked_file_count": 0, "secret_plaintext_output": False, "public_production_direct_launch": "No-Go"},
    )

    summary = build_production_landing_precommit_closeout(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "ready"
    assert summary["precommit_landing_ready"] is True
    assert payload["controlled_internal_pilot"] == "Go"
    assert payload["accepted_precommit_missing_conditions"] == []
    assert payload["missing_conditions"] == []
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["remaining_real_production_gaps"] == ["business_system:real_business_system_required"]


def test_precommit_closeout_blocks_unexpected_run_packet_missing_condition(tmp_path: Path) -> None:
    dirs = {
        "production_landing_action_pack": tmp_path / "action",
        "controlled_pilot_run_packet": tmp_path / "run_packet",
        "real_integration_staging_smoke": tmp_path / "infra",
        "production_landing_final_verification": tmp_path / "final",
        "production_landing_text_quality": tmp_path / "text_quality",
    }
    _write_json(
        dirs["production_landing_action_pack"],
        "001_production_landing_action_pack.json",
        {"status": "success", "required_input_count": 0, "public_production_direct_launch": "No-Go", "secret_plaintext_output": False},
    )
    _write_json(
        dirs["controlled_pilot_run_packet"],
        "001_controlled_pilot_run_packet.json",
        {
            "status": "partial",
            "controlled_internal_pilot": "Manual-Review",
            "missing_conditions": ["controlled_pilot_console_verify:latest_report_missing"],
            "public_production_direct_launch": "No-Go",
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["real_integration_staging_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "status": "success",
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["production_landing_final_verification"],
        "001_production_landing_final_verification.json",
        {"status": "partial", "secret_plaintext_output": False},
    )
    _write_json(
        dirs["production_landing_text_quality"],
        "001_production_landing_text_quality.json",
        {"status": "success", "blocked_file_count": 0, "secret_plaintext_output": False},
    )

    summary = build_production_landing_precommit_closeout(output_dir=tmp_path / "out", source_dirs=dirs)
    payload = _payload(summary)

    assert summary["status"] == "blocked"
    assert summary["precommit_landing_ready"] is False
    assert "run_packet:unexpected_missing_condition:controlled_pilot_console_verify:latest_report_missing" in payload[
        "missing_conditions"
    ]


def test_precommit_closeout_doc_keeps_boundaries() -> None:
    text = Path("docs/production_landing_precommit_closeout_v49.md").read_text(encoding="utf-8")

    assert "预提交" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "business_system:real_business_system_required" in text
    assert "post_commit_required=true" in text
    assert "不等于公网生产直接上线" in text
    assert "scripts\\production_landing_precommit_closeout.py" in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_precommit_closeout_is_discoverable_from_action_pack_and_text_quality() -> None:
    import scripts.production_landing_text_quality_check as text_quality
    from scripts import production_landing_action_pack as action_pack

    targets = {path.as_posix() for path in text_quality.DEFAULT_TARGETS}
    commands = "\n".join(action_pack._build_commands({"latest_launch_blockers": "x", "closure_evidence_draft": "x", "latest_closure_index": "x", "manual_signoff_record_draft": "x", "manual_signoff_record": "x"}))

    assert (text_quality.ROOT_DIR / "docs" / "production_landing_precommit_closeout_v49.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "production_landing_precommit_closeout.py").as_posix() in targets
    assert "scripts\\production_landing_precommit_closeout.py" in commands
