from __future__ import annotations

import json
from pathlib import Path

from scripts import manual_signoff_evidence_ack_status as status
from scripts.manual_signoff_evidence_ack_status import build_manual_signoff_evidence_ack_status


def _write_json(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _patch_report_specs(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    dirs = {
        "real_llm_preflight": tmp_path / "xiaomi",
        "postgres_redis_mcp_smoke": tmp_path / "infra",
        "business_read_smoke": tmp_path / "business",
        "closure_evidence_review": tmp_path / "closure",
    }
    monkeypatch.setattr(
        status,
        "REPORT_SPECS",
        {
            "real_llm_preflight": (dirs["real_llm_preflight"], "*_production_landing_xiaomi_llm_preflight.json"),
            "postgres_redis_mcp_smoke": (dirs["postgres_redis_mcp_smoke"], "*_real_integration_staging_smoke.json"),
            "business_read_smoke": (dirs["business_read_smoke"], "*_business_system_read_smoke.json"),
            "closure_evidence_review": (dirs["closure_evidence_review"], "*_launch_blocker_closure_workflow.json"),
        },
    )
    return dirs


def test_manual_signoff_evidence_ack_status_recommends_ready_items_only(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_report_specs(monkeypatch, tmp_path)
    _write_json(
        dirs["real_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {
            "status": "skipped",
            "real_llm_executed": False,
            "preflight": {"network_check_executed": False},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["postgres_redis_mcp_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "status": "success",
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_read_smoke"],
        "001_business_system_read_smoke.json",
        {
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["closure_evidence_review"],
        "001_launch_blocker_closure_workflow.json",
        {
            "status": "partial",
            "closure_item_count": 13,
            "review_ready_count": 13,
            "evidence_incomplete_count": 0,
        },
    )

    summary = build_manual_signoff_evidence_ack_status(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    by_id = {item["item"]: item for item in payload["items"]}

    assert summary["status"] == "partial"
    assert summary["recommended_accept_count"] == 3
    assert by_id["real_llm_preflight"]["recommended_accept"] is False
    assert "real_llm_preflight:status_not_success" in by_id["real_llm_preflight"]["missing_conditions"]
    assert by_id["postgres_redis_mcp_smoke"]["recommended_accept"] is True
    assert by_id["business_read_smoke"]["recommended_accept"] is True
    assert by_id["closure_evidence_review"]["recommended_accept"] is True
    assert payload["auto_approved"] is False
    assert payload["public_production_direct_launch"] == "No-Go"


def test_manual_signoff_evidence_ack_status_success_when_all_evidence_ready(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_report_specs(monkeypatch, tmp_path)
    _write_json(
        dirs["real_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {
            "status": "success",
            "real_llm_executed": True,
            "preflight": {"network_check_executed": True},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["postgres_redis_mcp_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "status": "success",
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_read_smoke"],
        "001_business_system_read_smoke.json",
        {
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["closure_evidence_review"],
        "001_launch_blocker_closure_workflow.json",
        {
            "status": "partial",
            "closure_item_count": 13,
            "review_ready_count": 13,
            "evidence_incomplete_count": 0,
        },
    )

    summary = build_manual_signoff_evidence_ack_status(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert summary["recommended_accept_count"] == 4
    assert all(item["recommended_accept"] is True for item in payload["items"])
    assert payload["secret_plaintext_output"] is False


def test_manual_signoff_evidence_ack_status_accepts_optional_infra_gap_for_controlled_pilot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_report_specs(monkeypatch, tmp_path)
    _write_json(
        dirs["real_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {
            "status": "success",
            "real_llm_executed": True,
            "preflight": {"network_check_executed": True},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["postgres_redis_mcp_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "status": "skipped",
            "database_connected": False,
            "redis_connected": False,
            "external_mcp_connected": False,
            "required_env": ["XIAOMI_LLM_API_KEY=<secret-managed-token>"],
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_read_smoke"],
        "001_business_system_read_smoke.json",
        {
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["closure_evidence_review"],
        "001_launch_blocker_closure_workflow.json",
        {"status": "partial", "closure_item_count": 1, "review_ready_count": 1, "evidence_incomplete_count": 0},
    )

    summary = build_manual_signoff_evidence_ack_status(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    infra = next(item for item in payload["items"] if item["item"] == "postgres_redis_mcp_smoke")

    assert summary["status"] == "success"
    assert infra["recommended_accept"] is True
    assert "postgres_redis_mcp_smoke:status_not_success_or_partial" in infra["missing_conditions"]
    assert "postgres_redis_mcp_smoke:database_connected_not_true" in infra["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"


def test_manual_signoff_evidence_ack_status_accepts_optional_business_read_gap_for_controlled_pilot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dirs = _patch_report_specs(monkeypatch, tmp_path)
    _write_json(
        dirs["real_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {
            "status": "success",
            "real_llm_executed": True,
            "preflight": {"network_check_executed": True},
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["postgres_redis_mcp_smoke"],
        "001_real_integration_staging_smoke.json",
        {
            "status": "success",
            "database_connected": True,
            "redis_connected": True,
            "external_mcp_connected": True,
            "migration_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["business_read_smoke"],
        "001_business_system_read_smoke.json",
        {
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "business_write_executed": False,
            "business_data_written": False,
            "secret_plaintext_output": False,
        },
    )
    _write_json(
        dirs["closure_evidence_review"],
        "001_launch_blocker_closure_workflow.json",
        {"status": "partial", "closure_item_count": 1, "review_ready_count": 1, "evidence_incomplete_count": 0},
    )

    summary = build_manual_signoff_evidence_ack_status(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    business = next(item for item in payload["items"] if item["item"] == "business_read_smoke")

    assert summary["status"] == "success"
    assert business["recommended_accept"] is True
    assert "business_read_smoke:status_not_success" in business["missing_conditions"]
    assert "business_read_smoke:business_read_executed_not_true" in business["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"


def test_manual_signoff_evidence_ack_status_blocks_secret_like_payload(tmp_path: Path, monkeypatch) -> None:
    dirs = _patch_report_specs(monkeypatch, tmp_path)
    secret_value = "sk-" + "secret"
    _write_json(
        dirs["real_llm_preflight"],
        "001_production_landing_xiaomi_llm_preflight.json",
        {"status": "success", "real_llm_executed": True, "preflight": {"network_check_executed": True}, "api_key": secret_value},
    )

    summary = build_manual_signoff_evidence_ack_status(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    real_llm = next(item for item in payload["items"] if item["item"] == "real_llm_preflight")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert "real_llm_preflight:secret_like_value_detected" in real_llm["missing_conditions"]
    assert secret_value not in merged
