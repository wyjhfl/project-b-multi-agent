from __future__ import annotations

import json
from pathlib import Path

from scripts import production_landing_env_check as env_check_module
from scripts.production_landing_env_check import build_production_landing_env_check
from scripts.production_landing_env_template import build_production_landing_env_template


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_landing_env_check_reports_placeholders_without_leaking(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)

    summary = build_production_landing_env_check(
        env_path=env_path,
        output_dir=tmp_path / "out",
        xiaomi_preflight_report_dir=tmp_path / "missing_xiaomi_reports",
    )
    payload = _payload(summary)
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")

    assert summary["status"] == "partial"
    assert summary["env_file_present"] is True
    assert real_llm["ready_for_execute"] is False
    assert "XIAOMI_LLM_API_KEY" in real_llm["placeholder_keys"]
    assert real_llm["blocker_reason"] == "placeholder_env"
    assert "inject_xiaomi_api_key_in_process_env" in real_llm["next_action"]
    assert "scripts\\xiaomi_llm_landing_resume.ps1" in real_llm["next_action"]
    assert "replace_placeholder_keys_in_local_env" not in real_llm["next_action"]
    assert real_llm["command_after_fill"].endswith("scripts\\xiaomi_llm_preflight.ps1")
    assert "XIAOMI_LLM_API_KEY" in real_llm["required_env_keys"]
    assert payload["blocked_domain_count"] == payload["domain_count"]
    assert payload["secret_plaintext_output"] is False
    assert "<secret-managed-token>" not in json.dumps(payload, ensure_ascii=False)
    assert "tp-" not in json.dumps(payload, ensure_ascii=False)


def test_production_landing_env_check_success_with_filled_local_values_without_value_output(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    fake_llm_secret = "tp-" + "local-real-secret-not-output"
    env_path.write_text(
        "\n".join(
            [
                "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
                "REAL_LLM_STAGING_SMOKE_EXECUTE=true",
                "REAL_LLM_ACCEPTANCE_ENABLED=true",
                "REAL_LLM_PREFLIGHT_ENABLED=true",
                "REAL_LLM_SMOKE_ENABLED=true",
                "REAL_LLM_PREFLIGHT_NETWORK_CHECK=true",
                "REAL_LLM_PROVIDER=litellm",
                "REAL_LLM_MODEL=mimo-v2.5-pro",
                "REAL_LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1",
                "REAL_LLM_API_KEY_ENV=XIAOMI_LLM_API_KEY",
                f"XIAOMI_LLM_API_KEY={fake_llm_secret}",
                "POSTGRES_STAGING_SMOKE_EXECUTE=true",
                "STORAGE_BACKEND=postgres",
                "DATABASE_URL=postgresql://user:pass@localhost/db",
                "REDIS_STAGING_SMOKE_EXECUTE=true",
                "REDIS_ENABLED=true",
                "REDIS_URL=redis://localhost:6379/0",
                "RATE_LIMIT_BACKEND=redis",
                "MCP_STAGING_SMOKE_EXECUTE=true",
                "MCP_MODE=real",
                "MCP_SERVER_COMMAND=fake-mcp",
                "MCP_SERVER_COMMAND_ALLOWLIST=fake-mcp",
                "MCP_TOOL_ALLOWLIST=safe_tool",
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
                "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
                "BUSINESS_SYSTEM_BASE_URL=https://business.example.test",
                "BUSINESS_SYSTEM_TOKEN=business-local-token-not-output",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=wyj",
                "BUSINESS_SYSTEM_SECURITY_REVIEWER=wyj",
                "BUSINESS_SYSTEM_OPERATIONS_OWNER=wyj",
                "BUSINESS_SYSTEM_DATA_OWNER=wyj",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_production_landing_env_check(
        env_path=env_path,
        output_dir=tmp_path / "out",
        xiaomi_preflight_report_dir=tmp_path / "missing_xiaomi_reports",
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "success"
    assert summary["ready_domain_count"] == summary["domain_count"]
    assert summary["blocked_domain_count"] == 0
    assert all(item["ready_for_execute"] for item in payload["domains"])
    assert all(item["blocker_reason"] == "" for item in payload["domains"])
    assert all(item["next_action"].startswith("run:") for item in payload["domains"])
    assert payload["secret_plaintext_output"] is False
    assert fake_llm_secret not in merged
    assert "postgresql://user:pass@localhost/db" not in merged
    assert "redis://localhost:6379/0" not in merged
    assert "business-local-token-not-output" not in merged


def test_production_landing_env_check_allows_process_env_over_secret_placeholder_without_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)
    monkeypatch.setenv("XIAOMI_LLM_API_KEY", "tp-process-secret-not-output")

    summary = build_production_landing_env_check(
        env_path=env_path,
        output_dir=tmp_path / "out",
        xiaomi_preflight_report_dir=tmp_path / "missing_xiaomi_reports",
    )
    payload = _payload(summary)
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert real_llm["ready_for_execute"] is True
    assert real_llm["placeholder_count"] == 0
    assert "XIAOMI_LLM_API_KEY" not in real_llm["placeholder_keys"]
    key_status = next(item for item in real_llm["keys"] if item["key"] == "XIAOMI_LLM_API_KEY")
    assert key_status["source"] == "process_env_over_env_file_placeholder"
    assert "tp-process-secret-not-output" not in merged


def test_production_landing_env_check_allows_successful_llm_preflight_evidence_without_key_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)
    report_dir = tmp_path / "reports" / "xiaomi"
    report_dir.mkdir(parents=True)
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "success",
        "api_key_present": True,
        "real_llm_executed": True,
        "secret_plaintext_output": False,
        "acceptance_blockers": [],
        "preflight": {"network_check_executed": True},
    }
    (report_dir / "001_production_landing_xiaomi_llm_preflight.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = build_production_landing_env_check(
        env_path=env_path,
        output_dir=tmp_path / "out",
        xiaomi_preflight_report_dir=report_dir,
    )
    result = _payload(summary)
    real_llm = next(item for item in result["domains"] if item["domain_id"] == "real_llm")

    assert real_llm["ready_for_execute"] is True
    assert real_llm["evidence_ready_override"] is True
    assert real_llm["evidence"]["ready"] is True
    assert real_llm["evidence"]["api_key_present"] is True
    assert real_llm["evidence"]["real_llm_executed"] is True
    assert real_llm["evidence"]["acceptance_blocker_count"] == 0
    assert real_llm["placeholder_count"] == 0


def test_production_landing_env_check_rejects_incomplete_llm_preflight_evidence_without_key_file(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)
    report_dir = tmp_path / "reports" / "xiaomi"
    report_dir.mkdir(parents=True)
    payload = {
        "generated_at": "2026-06-04T00:00:00+00:00",
        "status": "success",
        "real_llm_executed": True,
        "secret_plaintext_output": False,
        "preflight": {"network_check_executed": True},
    }
    (report_dir / "001_production_landing_xiaomi_llm_preflight.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = build_production_landing_env_check(
        env_path=env_path,
        output_dir=tmp_path / "out",
        xiaomi_preflight_report_dir=report_dir,
    )
    result = _payload(summary)
    real_llm = next(item for item in result["domains"] if item["domain_id"] == "real_llm")

    assert real_llm["ready_for_execute"] is False
    assert real_llm["evidence_ready_override"] is False
    assert real_llm["evidence"]["ready"] is False
    assert real_llm["evidence"]["api_key_present"] is False
    assert "XIAOMI_LLM_API_KEY" in real_llm["placeholder_keys"]


def test_production_landing_env_check_reports_secret_detection_flag_without_leak(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)
    monkeypatch.setitem(
        env_check_module.COMMAND_AFTER_FILL_BY_DOMAIN,
        "real_llm",
        "token=leaky-fixture-command",
    )

    summary = build_production_landing_env_check(
        env_path=env_path,
        output_dir=tmp_path / "out",
        xiaomi_preflight_report_dir=tmp_path / "missing_xiaomi_reports",
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "blocked"
    assert summary["secret_plaintext_output"] is True
    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert "leaky-fixture-command" not in merged
    assert "[redacted-secret-like-text]" in merged
