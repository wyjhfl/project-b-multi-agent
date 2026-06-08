from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.real_production_environment_checklist import build_real_production_environment_checklist

MOJIBAKE_MARKERS = ("鐪", "钀", "藉", "闆", "璐", "锛", "銆", "€")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _make_evidence_dirs(root: Path) -> dict[str, Path]:
    mapping = {
        "env_profile": root / "real_integration_env_profile",
        "real_llm_preflight": root / "production_landing_real_llm_preflight",
        "xiaomi_llm_preflight": root / "production_landing_xiaomi_llm_preflight",
        "staging_smoke": root / "real_integration_staging_smoke",
        "staging_gate": root / "real_integration_staging_gate",
        "gap_register": root / "real_integration_gap_register",
        "business_read_smoke": root / "business_system_read_smoke",
    }
    for directory in mapping.values():
        directory.mkdir(parents=True, exist_ok=True)
    return mapping


def _write_json(directory: Path, payload: dict, name: str = "001.json") -> None:
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_evidence(*, status: str = "partial") -> dict:
    return {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "version": "demo",
        "phase": "demo",
        "status": status,
        "read_only": True,
        "missing_conditions": [],
        "real_llm_executed": False,
        "database_connected": False,
        "redis_connected": False,
        "external_mcp_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
    }


def _successful_llm_preflight() -> dict:
    return {
        **_base_evidence(status="success"),
        "api_key_present": True,
        "real_llm_executed": True,
        "preflight": {
            "network_check_allowed": True,
            "network_check_executed": True,
        },
        "acceptance_blockers": [],
        "secret_plaintext_output": False,
    }


def test_real_production_environment_checklist_generates_default_report(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["status"] == "skipped"
    assert payload["version"] == "4.5.0"
    assert payload["read_only"] is True
    assert payload["domain_count"] == 5
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert "v4.5 真实生产环境落地 Checklist" in markdown
    assert not any(marker in markdown for marker in MOJIBAKE_MARKERS)


def test_real_production_environment_checklist_covers_real_domains_and_commands(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for directory in evidence_dirs.values():
        _write_json(directory, _base_evidence(status="partial"))

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    domains = {item["domain_id"]: item for item in payload["domains"]}

    assert payload["status"] == "partial"
    assert set(domains) == {"real_llm", "postgres", "redis", "external_mcp", "business_system"}
    assert domains["real_llm"]["smoke_command"].endswith("scripts\\real_llm_preflight.ps1")
    assert domains["real_llm"]["compat_smoke_command"].endswith("scripts\\xiaomi_llm_preflight.ps1")
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains postgres" in domains["postgres"]["smoke_command"]
    assert "-UseExistingEnv -EnvPath local\\production_landing.staging.env" in domains["postgres"]["smoke_command"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains redis" in domains["redis"]["smoke_command"]
    assert "-UseExistingEnv -EnvPath local\\production_landing.staging.env" in domains["redis"]["smoke_command"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp" in domains["external_mcp"]["smoke_command"]
    assert "-UseExistingEnv -EnvPath local\\production_landing.staging.env" in domains["external_mcp"]["smoke_command"]
    assert domains["business_system"]["smoke_command"].endswith("scripts\\business_system_read_smoke.ps1")
    assert domains["real_llm"]["owner"] == "LLM 集成负责人"
    assert "通用 real LLM preflight 网络检查通过" in domains["real_llm"]["required_evidence"]
    assert "Alembic migration 仅在人工批准窗口执行" in domains["postgres"]["required_config"]
    assert "断连降级、恢复、告警证据" in domains["redis"]["required_evidence"]
    assert "ToolGateway discovery/call 二次 allowlist 证据" in domains["external_mcp"]["required_evidence"]
    assert "REAL_LLM_ACCEPTANCE_ENABLED=true" in domains["real_llm"]["required_config"]
    assert "STORAGE_BACKEND=postgres" in domains["postgres"]["required_config"]
    assert "RATE_LIMIT_BACKEND=redis" in domains["redis"]["required_config"]
    assert "MCP_MODE=real" in domains["external_mcp"]["required_config"]
    assert "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe" in domains["business_system"]["required_config"]


def test_real_production_environment_checklist_marks_business_mock_as_not_real_acceptance(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "business_read_smoke":
            payload.update(
                {
                    "status": "success",
                    "business_system_connected": True,
                    "business_read_executed": True,
                    "business_write_executed": False,
                    "business_data_written": False,
                    "local_business_mock_used": True,
                    "secret_plaintext_output": False,
                }
            )
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    business = {item["domain_id"]: item for item in payload["domains"]}["business_system"]

    assert business["status"] == "partial"
    assert "business_system:real_read_smoke_not_executed" in business["missing_conditions"]
    assert payload["evidence"]["business_read_smoke"]["safe_summary"]["local_business_mock_used"] is True


def test_real_production_environment_checklist_accepts_real_business_read_evidence(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "business_read_smoke":
            payload.update(
                {
                    "status": "success",
                    "business_system_connected": True,
                    "business_read_executed": True,
                    "business_write_executed": False,
                    "business_data_written": False,
                    "local_business_mock_used": False,
                    "secret_plaintext_output": False,
                }
            )
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    business = {item["domain_id"]: item for item in payload["domains"]}["business_system"]

    assert business["status"] == "partial"
    assert "business_system:real_read_smoke_not_executed" not in business["missing_conditions"]
    assert "business_system:read_not_executed" not in business["missing_conditions"]


def test_real_production_environment_checklist_marks_unexecuted_real_domains(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for directory in evidence_dirs.values():
        _write_json(directory, _base_evidence(status="partial"))

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    domains = {item["domain_id"]: item for item in payload["domains"]}

    assert "real_llm:not_executed" in domains["real_llm"]["missing_conditions"]
    assert "postgres:database_not_connected" in domains["postgres"]["missing_conditions"]
    assert "redis:not_connected" in domains["redis"]["missing_conditions"]
    assert "external_mcp:not_connected" in domains["external_mcp"]["missing_conditions"]


def test_real_production_environment_checklist_clears_real_domain_execution_gaps(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "staging_smoke":
            payload.update(
                {
                    "real_llm_executed": True,
                    "database_connected": True,
                    "redis_connected": True,
                    "external_mcp_connected": True,
                    "secret_plaintext_output": False,
                }
            )
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    domains = {item["domain_id"]: item for item in payload["domains"]}

    assert "real_llm:not_executed" not in domains["real_llm"]["missing_conditions"]
    assert "postgres:database_not_connected" not in domains["postgres"]["missing_conditions"]
    assert "redis:not_connected" not in domains["redis"]["missing_conditions"]
    assert "external_mcp:not_connected" not in domains["external_mcp"]["missing_conditions"]


def test_real_production_environment_checklist_uses_aggregated_safe_infra_evidence(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "staging_smoke":
            payload.update(
                {
                    "status": "skipped",
                    "real_llm_executed": False,
                    "database_connected": False,
                    "redis_connected": False,
                    "external_mcp_connected": False,
                    "aggregated_infra_flags": {
                        "database_connected": True,
                        "redis_connected": True,
                        "external_mcp_connected": True,
                    },
                    "aggregated_evidence_paths": {
                        "database_connected": "docs/reports/real_integration_staging_smoke/safe.json",
                    },
                    "aggregated_safe_report_count": 1,
                    "aggregated_secret_report_count": 0,
                    "aggregated_unsafe_report_count": 0,
                    "secret_plaintext_output": False,
                }
            )
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    domains = {item["domain_id"]: item for item in payload["domains"]}

    assert "real_llm:not_executed" in domains["real_llm"]["missing_conditions"]
    assert "postgres:database_not_connected" not in domains["postgres"]["missing_conditions"]
    assert "redis:not_connected" not in domains["redis"]["missing_conditions"]
    assert "external_mcp:not_connected" not in domains["external_mcp"]["missing_conditions"]
    assert payload["evidence"]["staging_smoke"]["safe_summary"]["aggregated_safe_report_count"] == 1


def test_real_production_environment_checklist_accepts_generic_real_llm_preflight_evidence(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "staging_smoke":
            payload.update({"status": "skipped", "real_llm_executed": False, "secret_plaintext_output": False})
        if key == "real_llm_preflight":
            payload = _successful_llm_preflight()
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    real_llm = {item["domain_id"]: item for item in payload["domains"]}["real_llm"]

    assert payload["real_llm_evidence_source"] == "real_llm_preflight"
    assert "real_llm:not_executed" not in real_llm["missing_conditions"]
    assert "staging_smoke:report_missing_or_skipped" not in real_llm["missing_conditions"]
    assert payload["evidence"]["real_llm_preflight"]["safe_summary"]["api_key_present"] is True
    assert payload["evidence"]["real_llm_preflight"]["safe_summary"]["network_check_executed"] is True


def test_real_production_environment_checklist_accepts_xiaomi_fallback_when_generic_missing(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    # Leave generic report dir empty to exercise compatibility fallback.
    for key, directory in evidence_dirs.items():
        if key == "real_llm_preflight":
            continue
        payload = _base_evidence(status="partial")
        if key == "staging_smoke":
            payload.update({"status": "skipped", "real_llm_executed": False, "secret_plaintext_output": False})
        if key == "xiaomi_llm_preflight":
            payload = _successful_llm_preflight()
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    real_llm = {item["domain_id"]: item for item in payload["domains"]}["real_llm"]

    assert payload["real_llm_evidence_source"] == "xiaomi_llm_preflight"
    assert "real_llm:not_executed" not in real_llm["missing_conditions"]
    assert payload["evidence"]["xiaomi_llm_preflight"]["safe_summary"]["api_key_present"] is True


def test_real_production_environment_checklist_ignores_secret_like_xiaomi_when_generic_present(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "staging_smoke":
            payload.update({"status": "skipped", "real_llm_executed": False, "secret_plaintext_output": False})
        if key == "real_llm_preflight":
            payload = _successful_llm_preflight()
        if key == "xiaomi_llm_preflight":
            payload.update(
                {
                    "status": "blocked",
                    "api_key_present": True,
                    "real_llm_executed": True,
                    "preflight": {"network_check_executed": True},
                    "note": "api_key=sk-compat-xiaomi-secret",
                    "secret_plaintext_output": False,
                }
            )
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "partial"
    assert payload["real_llm_evidence_source"] == "real_llm_preflight"
    assert payload["evidence"]["xiaomi_llm_preflight"]["compat_ignored_by_generic_real_llm"] is True
    assert "sk-compat-xiaomi-secret" not in merged


def test_real_production_environment_checklist_blocks_secret_like_xiaomi_fallback_without_leaking(
    tmp_path: Path,
) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        if key == "real_llm_preflight":
            continue
        payload = _base_evidence(status="partial")
        if key == "xiaomi_llm_preflight":
            payload.update(
                {
                    "status": "success",
                    "api_key_present": True,
                    "real_llm_executed": True,
                    "preflight": {
                        "network_check_allowed": True,
                        "network_check_executed": True,
                    },
                    "note": "api_key=sk-sensitive-xiaomi-value",
                    "secret_plaintext_output": False,
                }
            )
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    real_llm = {item["domain_id"]: item for item in payload["domains"]}["real_llm"]
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "sk-sensitive-xiaomi-value" not in merged
    assert payload["evidence"]["xiaomi_llm_preflight"]["secret_detected"] is True
    assert "xiaomi_llm_preflight:secret_like_text_detected" in real_llm["missing_conditions"]


def test_real_production_environment_checklist_blocks_secret_like_evidence_without_leaking(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "staging_smoke":
            payload["note"] = "token=sk-sensitive-value"
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert "sk-sensitive-value" not in merged
    assert payload["evidence"]["staging_smoke"]["secret_detected"] is True


def test_real_production_environment_checklist_allows_secret_managed_placeholders(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        payload = _base_evidence(status="partial")
        if key == "staging_smoke":
            payload["required_env"] = [
                "REAL_LLM_API_KEY=<secret-managed-token>",
                "DATABASE_URL=<secret-managed-url>",
            ]
        _write_json(directory, payload)

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["evidence"]["staging_smoke"]["secret_detected"] is False


def test_real_production_environment_checklist_prefers_generated_at_over_mtime(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for key, directory in evidence_dirs.items():
        if key == "staging_smoke":
            current = directory / "100_current.json"
            stale = directory / "999_stale.json"
            current.write_text(
                json.dumps(
                    {
                        **_base_evidence(status="partial"),
                        "generated_at": "2026-06-05T10:00:00+00:00",
                        "database_connected": True,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            stale.write_text(
                json.dumps(
                    {
                        **_base_evidence(status="skipped"),
                        "generated_at": "2026-06-05T09:00:00+00:00",
                        "database_connected": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.utime(current, (1, 1))
            os.utime(stale, (2, 2))
        else:
            _write_json(directory, _base_evidence(status="partial"))

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)

    assert payload["evidence"]["staging_smoke"]["latest_json_path"] == str(evidence_dirs["staging_smoke"] / "100_current.json")
    assert payload["evidence"]["staging_smoke"]["safe_summary"]["database_connected"] is True


def test_real_production_environment_checklist_preserves_global_no_go(tmp_path: Path) -> None:
    evidence_dirs = _make_evidence_dirs(tmp_path / "evidence")
    for directory in evidence_dirs.values():
        _write_json(directory, _base_evidence(status="partial"))

    summary = build_real_production_environment_checklist(output_dir=tmp_path / "out", evidence_dirs=evidence_dirs)
    payload = _read_payload(summary)

    assert "任一真实域仍无脱敏证据" in payload["global_no_go"]
    assert "public_production_direct_launch 被改成 Go" in payload["global_no_go"]
    assert all(item["manual_signoff_required"] is True for item in payload["domains"])
    assert all(item["production_direct_launch"] == "No-Go" for item in payload["domains"])
