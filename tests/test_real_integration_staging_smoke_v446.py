from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from scripts.real_integration_staging_smoke import (
    SmokeExecutionResult,
    build_real_integration_staging_smoke,
)


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_env(monkeypatch) -> None:
    for key in [
        "REAL_INTEGRATION_STAGING_SMOKE_ENABLED",
        "REAL_LLM_STAGING_SMOKE_EXECUTE",
        "POSTGRES_STAGING_SMOKE_EXECUTE",
        "REDIS_STAGING_SMOKE_EXECUTE",
        "MCP_STAGING_SMOKE_EXECUTE",
        "REAL_LLM_PREFLIGHT_ENABLED",
        "REAL_LLM_ACCEPTANCE_ENABLED",
        "REAL_LLM_SMOKE_ENABLED",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
        "REAL_LLM_MODEL",
        "REAL_LLM_API_KEY_ENV",
        "OPENAI_API_KEY",
        "STORAGE_BACKEND",
        "DATABASE_URL",
        "REDIS_ENABLED",
        "REDIS_URL",
        "RATE_LIMIT_BACKEND",
        "MCP_MODE",
        "MCP_SERVER_COMMAND",
        "MCP_SERVER_COMMAND_ALLOWLIST",
        "MCP_TOOL_ALLOWLIST",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_real_integration_staging_smoke_default_dry_run_does_not_execute(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    invoked: list[str] = []

    def executor(domain_id: str) -> SmokeExecutionResult:
        invoked.append(domain_id)
        return SmokeExecutionResult(status="success", evidence={"ok": True})

    summary = build_real_integration_staging_smoke(output_dir=tmp_path / "out", executor=executor)
    payload = _read_payload(summary)

    assert invoked == []
    assert payload["status"] == "skipped"
    assert payload["read_only"] is True
    assert payload["execution_mode"] == "read_only_smoke"
    assert payload["execute_requested"] is False
    assert payload["preflight_summary"]["ready_domain_count"] == 0
    assert payload["preflight_summary"]["domain_count"] == 4
    assert payload["preflight_summary"]["all_requested_domains_ready_for_execute"] is False
    assert payload["domains"][0]["preflight"]["required_env"]
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")
    assert "REAL_LLM_MODEL=gpt-5.5" in real_llm["preflight"]["required_env"]
    assert "REAL_LLM_BASE_URL=http://100.119.206.22:8300/v1" in real_llm["preflight"]["required_env"]
    assert "REAL_LLM_API_KEY_ENV=REAL_LLM_API_KEY" in real_llm["preflight"]["required_env"]
    assert "REAL_LLM_API_KEY=<secret-managed-token>" in real_llm["preflight"]["required_env"]
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["migration_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"
    assert Path(summary["markdown_path"]).exists()


def test_real_integration_staging_smoke_execute_without_global_opt_in_blocks(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    invoked: list[str] = []

    def executor(domain_id: str) -> SmokeExecutionResult:
        invoked.append(domain_id)
        return SmokeExecutionResult(status="success", evidence={"ok": True})

    summary = build_real_integration_staging_smoke(
        output_dir=tmp_path / "out",
        execute=True,
        domains=["postgres"],
        executor=executor,
    )
    payload = _read_payload(summary)

    assert invoked == []
    assert payload["status"] == "blocked"
    assert "opt_in:REAL_INTEGRATION_STAGING_SMOKE_ENABLED" in payload["missing_conditions"]
    assert payload["real_llm_executed"] is False
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["external_mcp_connected"] is False


def test_real_integration_staging_smoke_executes_only_ready_opted_in_domain(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("POSTGRES_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "placeholder-not-a-url")
    invoked: list[str] = []

    def executor(domain_id: str) -> SmokeExecutionResult:
        invoked.append(domain_id)
        return SmokeExecutionResult(status="success", evidence={"sanitized_probe": "ok"})

    summary = build_real_integration_staging_smoke(
        output_dir=tmp_path / "out",
        execute=True,
        domains=["postgres"],
        executor=executor,
    )
    payload = _read_payload(summary)
    postgres = next(item for item in payload["domains"] if item["domain_id"] == "postgres")

    assert invoked == ["postgres"]
    assert payload["status"] == "success"
    assert payload["requested_domains"] == ["postgres"]
    assert [item["domain_id"] for item in payload["domains"]] == ["postgres"]
    assert postgres["status"] == "success"
    assert postgres["execution_invoked"] is True
    assert postgres["preflight"]["ready_for_execute"] is True
    assert "DATABASE_URL=<secret-managed-url>" in postgres["preflight"]["required_env"]
    assert payload["preflight_summary"]["ready_domains"] == ["postgres"]
    assert payload["database_connected"] is True
    assert payload["real_llm_executed"] is False


def test_real_integration_staging_smoke_blocks_placeholder_target_secret(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "mimo-v2.5-pro")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "XIAOMI_LLM_API_KEY")
    monkeypatch.setenv("XIAOMI_LLM_API_KEY", "<secret-managed-token>")
    invoked: list[str] = []

    def executor(domain_id: str) -> SmokeExecutionResult:
        invoked.append(domain_id)
        return SmokeExecutionResult(status="success", evidence={"ok": True})

    summary = build_real_integration_staging_smoke(
        output_dir=tmp_path / "out",
        execute=True,
        domains=["real_llm"],
        executor=executor,
    )
    payload = _read_payload(summary)
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")

    assert invoked == []
    assert payload["status"] == "blocked"
    assert "env_target:REAL_LLM_API_KEY_ENV" in real_llm["missing_conditions"]
    assert payload["real_llm_executed"] is False


def test_real_integration_staging_smoke_all_domains_success_with_injected_executor(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("POSTGRES_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("REDIS_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("MCP_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-real-secret")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "placeholder-not-a-url")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "placeholder-not-a-url")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "fake-mcp-server")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "fake-mcp-server")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")

    def executor(domain_id: str) -> SmokeExecutionResult:
        return SmokeExecutionResult(status="success", evidence={"result": f"{domain_id}:ok"})

    summary = build_real_integration_staging_smoke(output_dir=tmp_path / "out", execute=True, executor=executor)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "success"
    assert payload["read_only"] is True
    assert payload["execution_mode"] == "read_only_smoke"
    assert payload["preflight_summary"]["all_requested_domains_ready_for_execute"] is True
    assert payload["real_llm_executed"] is True
    assert payload["database_connected"] is True
    assert payload["redis_connected"] is True
    assert payload["external_mcp_connected"] is True
    assert payload["migration_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert "sk-sensitive-real-secret" not in merged
    assert payload["go_no_go"]["public_production_direct_launch"] == "No-Go"


def test_real_integration_staging_smoke_blocks_secret_like_executor_output(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("POSTGRES_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "placeholder-not-a-url")

    def executor(domain_id: str) -> SmokeExecutionResult:
        return SmokeExecutionResult(status="success", evidence={"note": "token=sk-sensitive-value"})

    summary = build_real_integration_staging_smoke(output_dir=tmp_path / "out", execute=True, executor=executor)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    postgres = next(item for item in payload["domains"] if item["domain_id"] == "postgres")
    assert "executor_output_secret_like_text_detected" in postgres["errors"]
    assert "sk-sensitive-value" not in merged
    assert "[redacted-secret-like-text]" in merged


def test_real_integration_staging_smoke_blocks_invalid_domain(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)

    summary = build_real_integration_staging_smoke(
        output_dir=tmp_path / "out",
        domains=["postgres", "unknown_domain"],
    )
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert payload["requested_domains"] == ["postgres", "unknown_domain"]
    assert payload["invalid_domains"] == ["unknown_domain"]
    assert "domain:unknown_domain:unsupported" in payload["missing_conditions"]


def test_real_integration_staging_smoke_default_executor_uses_llm_preflight(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_ACCEPTANCE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REAL_LLM_PREFLIGHT_NETWORK_CHECK", "true")
    monkeypatch.setenv("REAL_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("REAL_LLM_API_KEY_ENV", "OPENAI_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-sensitive-real-secret")

    class FakePreflightResult:
        def to_dict(self) -> dict:
            return {
                "status": "passed",
                "provider": "litellm",
                "model": "gpt-test",
                "api_key_env": "OPENAI_API_KEY",
                "api_key_present": True,
                "network_check_executed": True,
                "latency_ms": 12.5,
                "checks": [{"name": "network_check", "ok": True}],
                "errors": [],
                "warnings": [],
            }

    fake_module = types.ModuleType("app.harness.llm.preflight")
    fake_module.run_llm_provider_preflight = lambda perform_network_check=False: FakePreflightResult()
    monkeypatch.setitem(sys.modules, "app.harness.llm.preflight", fake_module)

    summary = build_real_integration_staging_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)
    real_llm = next(item for item in payload["domains"] if item["domain_id"] == "real_llm")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert real_llm["status"] == "success"
    assert real_llm["execution_invoked"] is True
    assert payload["real_llm_executed"] is True
    assert "sk-sensitive-real-secret" not in merged


def test_real_integration_staging_smoke_default_executor_uses_database_health(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("POSTGRES_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "placeholder-not-a-url")

    fake_module = types.ModuleType("app.storage.database")
    fake_module.check_database_health = lambda: {"status": "ok", "backend": "postgres"}
    monkeypatch.setitem(sys.modules, "app.storage.database", fake_module)

    summary = build_real_integration_staging_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)
    postgres = next(item for item in payload["domains"] if item["domain_id"] == "postgres")

    assert postgres["status"] == "success"
    assert postgres["evidence"]["backend"] == "postgres"
    assert payload["database_connected"] is True


def test_real_integration_staging_smoke_default_executor_uses_redis_health(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("REDIS_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "placeholder-not-a-url")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")

    fake_module = types.ModuleType("app.cache.redis_client")
    fake_module.check_redis_health = lambda: {"status": "ok", "backend": "redis"}
    monkeypatch.setitem(sys.modules, "app.cache.redis_client", fake_module)

    summary = build_real_integration_staging_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)
    redis = next(item for item in payload["domains"] if item["domain_id"] == "redis")

    assert redis["status"] == "success"
    assert redis["evidence"]["backend"] == "redis"
    assert payload["redis_connected"] is True


def test_real_integration_staging_smoke_default_executor_uses_mcp_list_tools(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv("REAL_INTEGRATION_STAGING_SMOKE_ENABLED", "true")
    monkeypatch.setenv("MCP_STAGING_SMOKE_EXECUTE", "true")
    monkeypatch.setenv("MCP_MODE", "real")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "fake-mcp-server")
    monkeypatch.setenv("MCP_SERVER_COMMAND_ALLOWLIST", "fake-mcp-server")
    monkeypatch.setenv("MCP_TOOL_ALLOWLIST", "safe_tool")

    class FakeMCPClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def list_tools(self):
            from app.tools.mcp.client import MCPToolInfo

            return [
                MCPToolInfo(
                    name="safe_tool",
                    description="Safe test tool",
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
                    risk_level="low",
                    permission_scope="read",
                ),
                MCPToolInfo(
                    name="blocked_tool",
                    description="Blocked test tool",
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
                    risk_level="high",
                    permission_scope="write",
                ),
            ]

        def call_tool(self, name, arguments):
            return {"ok": name == "safe_tool", "name": name}

        def get_health(self):
            return {"started": True, "initialized": True, "failure_count": 0}

        def close(self):
            return None

    fake_module = types.ModuleType("app.tools.mcp.stdio_client")
    fake_module.StdioMCPClient = FakeMCPClient
    monkeypatch.setitem(sys.modules, "app.tools.mcp.stdio_client", fake_module)

    summary = build_real_integration_staging_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)
    external_mcp = next(item for item in payload["domains"] if item["domain_id"] == "external_mcp")

    assert external_mcp["status"] == "success"
    assert external_mcp["evidence"]["tools_list_executed"] is True
    assert external_mcp["evidence"]["tool_count"] == 1
    assert external_mcp["evidence"]["tool_allowlist_enforced"] is True
    assert external_mcp["evidence"]["allowed_tool_names"] == ["safe_tool"]
    assert external_mcp["evidence"]["gateway_call_executed"] is True
    assert external_mcp["evidence"]["gateway_call_success"] is True
    assert payload["external_mcp_connected"] is True
