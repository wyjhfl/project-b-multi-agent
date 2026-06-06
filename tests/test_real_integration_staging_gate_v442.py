from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.real_integration_staging_gate import build_real_integration_staging_gate


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _make_evidence_dirs(root: Path) -> dict[str, Path]:
    mapping = {
        "real_integration_env_profile": root / "real_integration_env_profile",
        "real_integration_smoke_plan": root / "real_integration_smoke_plan",
        "real_integration_staging_smoke": root / "real_integration_staging_smoke",
        "real_integration_readiness": root / "real_integration_readiness",
        "real_llm_provider_acceptance_gate": root / "real_llm_provider_acceptance_gate",
        "external_mcp_acceptance_gate": root / "external_mcp_acceptance_gate",
        "store_redis_readiness_drill": root / "store_redis_readiness_drill",
        "production_migration_drill": root / "production_migration_drill",
    }
    for directory in mapping.values():
        directory.mkdir(parents=True, exist_ok=True)
    return mapping


def _write_json(directory: Path, name: str, payload: dict) -> None:
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_safe_payload(*, status: str) -> dict:
    return {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "phase": "demo-phase",
        "version": "demo-version",
        "status": status,
        "read_only": True,
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "missing_conditions": [],
    }


def test_real_integration_staging_gate_generates_json_and_markdown(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert payload["phase"] == "v4.4 Phase 24.5"
    assert payload["version"] == "4.4.2"
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["migration_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert Path(summary["json_path"]).exists()
    assert Path(summary["markdown_path"]).exists()


def test_real_integration_staging_gate_missing_evidence_is_skipped(tmp_path: Path) -> None:
    evidence_dirs = {
        "real_integration_env_profile": tmp_path / "missing-env-profile",
        "real_integration_smoke_plan": tmp_path / "missing-smoke-plan",
        "real_integration_staging_smoke": tmp_path / "missing-staging-smoke",
        "real_integration_readiness": tmp_path / "missing-a",
        "real_llm_provider_acceptance_gate": tmp_path / "missing-b",
        "external_mcp_acceptance_gate": tmp_path / "missing-c",
        "store_redis_readiness_drill": tmp_path / "missing-d",
        "production_migration_drill": tmp_path / "missing-e",
    }

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)

    assert payload["status"] == "skipped"
    assert payload["go_no_go"]["combined_staging_gate"] == "Needs-Input"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert all(item["status"] == "skipped" for item in payload["evidence_index"])


def test_real_integration_staging_gate_partial_and_manual_review_with_six_sanitized_evidence_dirs(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(evidence_dirs["real_integration_env_profile"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_smoke_plan"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_readiness"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_llm_provider_acceptance_gate"], "001.json", _base_safe_payload(status="success"))
    _write_json(evidence_dirs["external_mcp_acceptance_gate"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["store_redis_readiness_drill"], "001.json", _base_safe_payload(status="success"))
    _write_json(evidence_dirs["production_migration_drill"], "001.json", _base_safe_payload(status="success"))

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["go_no_go"]["combined_staging_gate"] == "Manual-Review"
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert all(item["status"] == "partial" for item in payload["evidence_index"])
    assert payload["evidence_count"] == 8


def test_real_integration_staging_gate_prefers_successful_controlled_evidence_over_latest_skipped(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(evidence_dirs["real_integration_env_profile"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_smoke_plan"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_readiness"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_llm_provider_acceptance_gate"], "001.json", _base_safe_payload(status="success"))
    _write_json(evidence_dirs["external_mcp_acceptance_gate"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["store_redis_readiness_drill"], "001.json", _base_safe_payload(status="success"))

    success_smoke = _base_safe_payload(status="success")
    success_smoke["real_llm_executed"] = True
    success_smoke["database_connected"] = True
    success_smoke["redis_connected"] = True
    success_smoke["external_mcp_connected"] = True
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001_success.json", success_smoke)
    _write_json(evidence_dirs["real_integration_staging_smoke"], "999_latest_skipped.json", _base_safe_payload(status="skipped"))

    migration = _base_safe_payload(status="success")
    migration["database_connected"] = True
    migration["migration_executed"] = True
    _write_json(evidence_dirs["production_migration_drill"], "001_success.json", migration)
    _write_json(evidence_dirs["production_migration_drill"], "999_latest_skipped.json", _base_safe_payload(status="skipped"))

    summary = build_real_integration_staging_gate(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=evidence_dirs["real_integration_staging_smoke"],
    )
    payload = _read_payload(summary)
    smoke = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_smoke")
    migration_item = next(item for item in payload["evidence_index"] if item["evidence_id"] == "production_migration_drill")

    assert payload["status"] == "partial"
    assert smoke["status"] == "partial"
    assert smoke["latest_json_path"].endswith("001_success.json")
    assert migration_item["status"] == "partial"
    assert migration_item["latest_json_path"].endswith("001_success.json")
    assert payload["blocking_reasons"] == []


def test_real_integration_staging_gate_prefers_generated_at_with_same_rank(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        if key == "real_integration_staging_smoke":
            current = directory / "100_current.json"
            stale = directory / "999_stale.json"
            current_payload = {
                **_base_safe_payload(status="partial"),
                "generated_at": "2026-06-05T10:00:00+00:00",
                "database_connected": True,
            }
            stale_payload = {
                **_base_safe_payload(status="partial"),
                "generated_at": "2026-06-05T09:00:00+00:00",
                "database_connected": False,
            }
            current.write_text(json.dumps(current_payload, ensure_ascii=False), encoding="utf-8")
            stale.write_text(json.dumps(stale_payload, ensure_ascii=False), encoding="utf-8")
            os.utime(current, (1, 1))
            os.utime(stale, (2, 2))
        else:
            _write_json(directory, "001.json", _base_safe_payload(status="partial"))

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    smoke = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_smoke")

    assert smoke["latest_json_path"] == str(evidence_dirs["real_integration_staging_smoke"] / "100_current.json")
    assert smoke["safe_summary"]["database_connected"] is True


def test_real_integration_staging_gate_manual_review_when_controlled_domains_verified(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(evidence_dirs["real_integration_env_profile"], "001.json", _base_safe_payload(status="skipped"))
    _write_json(evidence_dirs["real_integration_smoke_plan"], "001.json", _base_safe_payload(status="skipped"))
    _write_json(evidence_dirs["real_integration_readiness"], "001.json", _base_safe_payload(status="skipped"))
    _write_json(evidence_dirs["real_llm_provider_acceptance_gate"], "001.json", _base_safe_payload(status="skipped"))
    _write_json(evidence_dirs["external_mcp_acceptance_gate"], "001.json", _base_safe_payload(status="skipped"))
    _write_json(evidence_dirs["store_redis_readiness_drill"], "001.json", _base_safe_payload(status="skipped"))

    success_smoke = _base_safe_payload(status="success")
    success_smoke["real_llm_executed"] = True
    success_smoke["database_connected"] = True
    success_smoke["redis_connected"] = True
    success_smoke["external_mcp_connected"] = True
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001_success.json", success_smoke)

    migration = _base_safe_payload(status="success")
    migration["database_connected"] = True
    migration["migration_executed"] = True
    _write_json(evidence_dirs["production_migration_drill"], "001_success.json", migration)

    summary = build_real_integration_staging_gate(
        output_dir=tmp_path / "out",
        evidence_dirs=evidence_dirs,
        historical_llm_report_dir=evidence_dirs["real_integration_staging_smoke"],
    )
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["go_no_go"]["combined_staging_gate"] == "Manual-Review"


def test_real_integration_staging_gate_blocks_secret_like_evidence_without_leaking_plaintext(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(evidence_dirs["real_integration_env_profile"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_smoke_plan"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_readiness"], "001.json", _base_safe_payload(status="partial"))
    secret_payload = _base_safe_payload(status="partial")
    secret_payload["notes"] = "token=sk-sensitive-value"
    _write_json(evidence_dirs["real_llm_provider_acceptance_gate"], "001.json", secret_payload)
    _write_json(evidence_dirs["external_mcp_acceptance_gate"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["store_redis_readiness_drill"], "001.json", _base_safe_payload(status="partial"))

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "secret_like_content_detected" in payload["blocking_reasons"]
    assert "sk-sensitive-value" not in merged
    assert "token=sk-sensitive-value" not in merged


def test_real_integration_staging_gate_allows_secret_managed_placeholders(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_safe_payload(status="partial")
        if key == "real_integration_staging_smoke":
            payload["required_env"] = [
                "XIAOMI_LLM_API_KEY=<secret-managed-token>",
                "DATABASE_URL=<secret-managed-url>",
            ]
        _write_json(directory, "001.json", payload)

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    smoke = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_staging_smoke")

    assert payload["status"] == "partial"
    assert smoke["status"] == "partial"
    assert smoke["blocking_reasons"] == []


def test_real_integration_staging_gate_blocks_unexpected_execution_flags(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    _write_json(evidence_dirs["real_integration_env_profile"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_smoke_plan"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001.json", _base_safe_payload(status="partial"))
    abnormal_payload = _base_safe_payload(status="partial")
    abnormal_payload["real_llm_executed"] = True
    _write_json(evidence_dirs["real_integration_readiness"], "001.json", abnormal_payload)
    _write_json(evidence_dirs["real_llm_provider_acceptance_gate"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["external_mcp_acceptance_gate"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["store_redis_readiness_drill"], "001.json", _base_safe_payload(status="partial"))

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    readiness_item = next(item for item in payload["evidence_index"] if item["evidence_id"] == "real_integration_readiness")

    assert payload["status"] == "blocked"
    assert "unexpected_true_flag:real_llm_executed" in payload["blocking_reasons"]
    assert readiness_item["status"] == "blocked"


def test_real_integration_staging_gate_redacts_secret_like_paths(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "token=sk-sensitive-path" / "evidence")
    _write_json(evidence_dirs["real_integration_env_profile"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_smoke_plan"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_staging_smoke"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_integration_readiness"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["real_llm_provider_acceptance_gate"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["external_mcp_acceptance_gate"], "001.json", _base_safe_payload(status="partial"))
    _write_json(evidence_dirs["store_redis_readiness_drill"], "001.json", _base_safe_payload(status="partial"))

    summary = build_real_integration_staging_gate(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert "sk-sensitive-path" not in merged
    assert "[redacted-secret-like-path]" in merged
