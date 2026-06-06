from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.production_landing_env_template import build_production_landing_env_template
from scripts.production_landing_execution_gate import build_production_landing_execution_gate


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _isolate_xiaomi_reports(monkeypatch, tmp_path: Path) -> Path:
    report_dir = tmp_path / "missing_xiaomi_reports"
    monkeypatch.setenv("PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_REPORT_DIR", str(report_dir))
    return report_dir


def test_production_landing_execution_gate_blocks_placeholder_values_without_leaking(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)
    _isolate_xiaomi_reports(monkeypatch, tmp_path)

    summary = build_production_landing_execution_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")

    assert summary["status"] == "partial"
    assert summary["execution_allowed"] is False
    assert payload["ready_domain_count"] == 0
    assert payload["blocked_domain_count"] == payload["requested_domain_count"]
    assert "XIAOMI_LLM_API_KEY" in real_llm["placeholder_keys"]
    assert real_llm["blocker_reason"] == "placeholder_env"
    assert payload["safe_runner_commands"] == [
        "python scripts/production_landing_env_runner.py --action env-check",
        "python scripts/production_landing_env_runner.py --action xiaomi-llm-preflight",
        "python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check",
        "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1",
    ]
    assert payload["real_smoke_executed"] is False
    assert payload["business_smoke_executed"] is False
    assert payload["secret_plaintext_output"] is False
    assert "<secret-managed-token>" not in json.dumps(payload, ensure_ascii=False)
    assert "tp-" not in json.dumps(payload, ensure_ascii=False)


def test_production_landing_execution_gate_rejects_incomplete_llm_evidence_for_env_readiness(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)
    report_dir = tmp_path / "xiaomi_reports"
    report_dir.mkdir()
    monkeypatch.setenv("PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_REPORT_DIR", str(report_dir))
    (report_dir / "001_production_landing_xiaomi_llm_preflight.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T00:00:00+00:00",
                "status": "success",
                "real_llm_executed": True,
                "preflight": {"network_check_executed": True},
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = build_production_landing_execution_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")

    assert summary["execution_allowed"] is False
    assert "real_llm" in payload["blocked_domains"]
    assert "real_llm" not in payload["ready_domains"]
    assert "XIAOMI_LLM_API_KEY" in real_llm["placeholder_keys"]
    assert real_llm["blocker_reason"] == "placeholder_env"


def test_production_landing_execution_gate_allows_successful_llm_preflight_evidence_without_key_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    build_production_landing_env_template(output_path=env_path)
    report_dir = tmp_path / "xiaomi_reports"
    report_dir.mkdir()
    monkeypatch.setenv("PRODUCTION_LANDING_XIAOMI_LLM_PREFLIGHT_REPORT_DIR", str(report_dir))
    (report_dir / "001_production_landing_xiaomi_llm_preflight.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-06-05T00:00:00+00:00",
                "status": "success",
                "api_key_present": True,
                "real_llm_executed": True,
                "preflight": {"network_check_executed": True},
                "acceptance_blockers": [],
                "secret_plaintext_output": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = build_production_landing_execution_gate(env_path=env_path, output_dir=tmp_path / "out", domains="real_llm")
    payload = _payload(summary)
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")

    assert summary["execution_allowed"] is True
    assert payload["ready_domains"] == ["real_llm"]
    assert payload["blocked_domains"] == []
    assert real_llm["ready_for_execute"] is True
    assert real_llm["placeholder_keys"] == []
    assert real_llm["blocker_reason"] == ""
    assert payload["safe_runner_commands"] == [
        "python scripts/production_landing_env_runner.py --action env-check",
        "python scripts/production_landing_env_runner.py --action staging-smoke",
    ]


def test_production_landing_execution_gate_recommends_local_infra_smoke_when_postgres_redis_ready(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    _isolate_xiaomi_reports(monkeypatch, tmp_path)
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
                "XIAOMI_LLM_API_KEY=<secret-managed-token>",
                "POSTGRES_STAGING_SMOKE_EXECUTE=true",
                "STORAGE_BACKEND=postgres",
                "DATABASE_URL=postgresql+psycopg://agent:dev-only-password@localhost:5432/project_b",
                "REDIS_STAGING_SMOKE_EXECUTE=true",
                "REDIS_ENABLED=true",
                "REDIS_URL=redis://localhost:6379/0",
                "RATE_LIMIT_BACKEND=redis",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_production_landing_execution_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert payload["execution_allowed"] is False
    assert payload["ready_domains"] == ["postgres", "redis"]
    assert "python scripts/production_landing_env_runner.py --action xiaomi-llm-preflight" in payload["safe_runner_commands"]
    assert (
        "python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check"
        in payload["safe_runner_commands"]
    )
    assert "powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1" in payload["safe_runner_commands"]
    assert "python scripts/production_landing_env_runner.py --action local-infra-smoke" in payload["safe_runner_commands"]
    assert "python scripts/production_landing_env_runner.py --action staging-smoke" not in payload["safe_runner_commands"]


def test_production_landing_execution_gate_recommends_local_infra_mcp_smoke_when_mcp_ready(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    _isolate_xiaomi_reports(monkeypatch, tmp_path)
    env_path.write_text(
        "\n".join(
            [
                "POSTGRES_STAGING_SMOKE_EXECUTE=true",
                "STORAGE_BACKEND=postgres",
                "DATABASE_URL=postgresql+psycopg://agent:dev-only-password@localhost:5432/project_b",
                "REDIS_STAGING_SMOKE_EXECUTE=true",
                "REDIS_ENABLED=true",
                "REDIS_URL=redis://localhost:6379/0",
                "RATE_LIMIT_BACKEND=redis",
                "MCP_STAGING_SMOKE_EXECUTE=true",
                "MCP_MODE=real",
                "MCP_SERVER_COMMAND=python",
                "MCP_SERVER_COMMAND_ALLOWLIST=python",
                "MCP_TOOL_ALLOWLIST=stdio_date_lookup",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_production_landing_execution_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert payload["ready_domains"] == ["postgres", "redis", "external_mcp"]
    assert "python scripts/production_landing_env_runner.py --action local-infra-mcp-smoke" in payload["safe_runner_commands"]
    assert "python scripts/production_landing_env_runner.py --action local-infra-smoke" not in payload["safe_runner_commands"]
    assert "python scripts/production_landing_env_runner.py --action staging-smoke" not in payload["safe_runner_commands"]


def test_production_landing_execution_gate_allows_filled_requested_domains_without_value_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "landing.env"
    _isolate_xiaomi_reports(monkeypatch, tmp_path)
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

    summary = build_production_landing_execution_gate(
        env_path=env_path,
        output_dir=tmp_path / "out",
        domains="real_llm,postgres,redis,external_mcp,business_system",
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "success"
    assert summary["execution_allowed"] is True
    assert payload["all_requested_domains_ready_for_execute"] is True
    assert payload["safe_runner_commands"] == [
        "python scripts/production_landing_env_runner.py --action env-check",
        "python scripts/production_landing_env_runner.py --action local-infra-mcp-smoke",
        "python scripts/production_landing_env_runner.py --action local-business-smoke",
        "python scripts/production_landing_env_runner.py --action staging-smoke",
        "python scripts/production_landing_env_runner.py --action business-smoke",
    ]
    assert fake_llm_secret not in merged
    assert "postgresql://user:pass@localhost/db" not in merged
    assert "redis://localhost:6379/0" not in merged
    assert "business-local-token-not-output" not in merged


def test_production_landing_execution_gate_rejects_unknown_domain(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        build_production_landing_execution_gate(
            env_path=tmp_path / "landing.env",
            output_dir=tmp_path / "out",
            domains="real_llm,unknown",
        )
