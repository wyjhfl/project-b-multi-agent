from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.production_landing_env_runner import build_production_landing_env_runner, _child_domain_counts, _extract_child_status


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_landing_env_runner_runs_env_check_with_local_env_without_leaking(tmp_path: Path) -> None:
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

    summary = build_production_landing_env_runner(
        action="env-check",
        env_path=env_path,
        output_dir=tmp_path / "out",
        timeout_seconds=30,
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "success"
    assert payload["action"] == "env-check"
    assert payload["command"].startswith("python scripts/production_landing_env_check.py --env-path ")
    assert str(env_path) in payload["command"]
    assert "--output-dir" in payload["command"]
    assert "child_env_check" in payload["command"]
    assert "--xiaomi-preflight-report-dir" in payload["command"]
    assert "child_xiaomi_llm_preflight" in payload["command"]
    assert payload["return_code"] == 0
    assert payload["child_status"] == "success"
    assert payload["child_summary"]["status"] == "success"
    assert payload["child_summary"]["ready_domain_count"] == payload["child_summary"]["domain_count"]
    assert payload["secret_plaintext_output"] is False
    assert fake_llm_secret not in merged
    assert "postgresql://user:pass@localhost/db" not in merged
    assert "redis://localhost:6379/0" not in merged
    assert "business-local-token-not-output" not in merged


def test_production_landing_env_runner_propagates_partial_child_status(tmp_path: Path) -> None:
    env_path = tmp_path / "missing.env"

    summary = build_production_landing_env_runner(
        action="env-check",
        env_path=env_path,
        output_dir=tmp_path / "out",
        timeout_seconds=30,
    )
    payload = _payload(summary)

    assert summary["status"] == "partial"
    assert payload["return_code"] == 0
    assert payload["child_status"] == "partial"
    assert payload["child_summary"]["status"] == "partial"
    assert payload["child_summary"]["ready_domain_count"] == 0


def test_production_landing_env_runner_extracts_child_json_after_noisy_logs() -> None:
    stdout = "\n".join(
        [
            "noisy library warning",
            "2026-06-05 INFO SELECT 1",
            '{"status":"failed","ready_domain_count":2,"domain_count":4,"secret_plaintext_output":false}',
            "json_path=docs/reports/example.json",
        ]
    )

    status, payload = _extract_child_status(stdout, 0)

    assert status == "failed"
    assert payload["ready_domain_count"] == 2
    assert payload["domain_count"] == 4


def test_production_landing_env_runner_derives_child_domain_counts_from_domains() -> None:
    ready, total = _child_domain_counts(
        {
            "status": "success",
            "domains": [
                {"domain_id": "postgres", "status": "success"},
                {"domain_id": "redis", "status": "success"},
                {"domain_id": "external_mcp", "status": "blocked"},
            ],
        }
    )

    assert ready == 2
    assert total == 3


def test_production_landing_env_runner_derives_child_domain_counts_from_success_summary() -> None:
    ready, total = _child_domain_counts({"status": "success", "domain_count": 2})

    assert ready == 2
    assert total == 2


def test_production_landing_env_runner_rejects_unsupported_action(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        build_production_landing_env_runner(action="arbitrary", env_path=tmp_path / "env", output_dir=tmp_path / "out")


def test_production_landing_env_runner_supports_local_infra_smoke_action(tmp_path: Path, monkeypatch) -> None:
    import scripts.production_landing_env_runner as runner

    env_path = tmp_path / "landing.env"
    env_path.write_text("", encoding="utf-8")

    class FakeCompleted:
        returncode = 0
        stdout = '{"status":"success","ready_domain_count":2,"domain_count":2,"secret_plaintext_output":false}'
        stderr = ""

    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompleted()

    monkeypatch.setattr(runner, "_run_git", lambda args: "abc12345")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    summary = runner.build_production_landing_env_runner(
        action="local-infra-smoke",
        env_path=env_path,
        output_dir=tmp_path / "out",
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert "--domains" in captured["command"]
    assert "postgres,redis" in captured["command"]
    assert payload["child_summary"]["ready_domain_count"] == 2


def test_production_landing_env_runner_supports_xiaomi_llm_preflight_action(tmp_path: Path, monkeypatch) -> None:
    import scripts.production_landing_env_runner as runner

    env_path = tmp_path / "landing.env"
    env_path.write_text("XIAOMI_LLM_API_KEY=<secret-managed-token>\n", encoding="utf-8")
    child_payload_path = tmp_path / "child.json"
    child_payload_path.write_text(
        json.dumps(
            {
                "status": "skipped",
                "api_key_present": False,
                "execute_network_check": True,
                "real_llm_executed": False,
                "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
                "acceptance_blockers": [
                    "missing_process_env:XIAOMI_LLM_API_KEY",
                    "network_check_not_allowed_without_process_key",
                ],
                "preflight": {
                    "api_key_present": False,
                    "network_check_requested": True,
                    "network_check_allowed": False,
                    "network_check_executed": False,
                },
                "secret_plaintext_output": False,
            }
        ),
        encoding="utf-8",
    )

    class FakeCompleted:
        returncode = 0
        stdout = json.dumps(
            {
                "status": "skipped",
                "api_key_present": False,
                "json_path": str(child_payload_path),
                "execute_network_check": True,
                "real_llm_executed": False,
                "safe_next_action": "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely",
                "acceptance_blockers": [
                    "missing_process_env:XIAOMI_LLM_API_KEY",
                    "network_check_not_allowed_without_process_key",
                ],
                "preflight": {
                    "api_key_present": False,
                    "network_check_requested": True,
                    "network_check_allowed": False,
                    "network_check_executed": False,
                },
                "secret_plaintext_output": False,
            }
        )
        stderr = ""

    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompleted()

    monkeypatch.setattr(runner, "_run_git", lambda args: "abc12345")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    summary = runner.build_production_landing_env_runner(
        action="xiaomi-llm-preflight",
        env_path=env_path,
        output_dir=tmp_path / "out",
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "skipped"
    assert any("production_landing_xiaomi_llm_preflight_runner.py" in part for part in captured["command"])
    assert "--execute-network-check" in captured["command"]
    assert "--output-dir" in captured["command"]
    assert "docs/reports/production_landing_xiaomi_llm_preflight" in payload["command"]
    assert "child_xiaomi_llm_preflight" not in payload["command"]
    assert payload["child_summary"]["status"] == "skipped"
    assert payload["child_xiaomi_preflight"]["api_key_present"] is False
    assert payload["child_xiaomi_preflight"]["network_check_requested"] is True
    assert payload["child_xiaomi_preflight"]["network_check_allowed"] is False
    assert payload["child_xiaomi_preflight"]["network_check_executed"] is False
    assert payload["child_xiaomi_preflight"]["real_llm_executed"] is False
    assert (
        payload["child_xiaomi_preflight"]["safe_next_action"]
        == "run_scripts_xiaomi_llm_preflight_ps1_and_enter_key_securely"
    )
    assert "missing_process_env:XIAOMI_LLM_API_KEY" in payload["child_xiaomi_preflight"]["acceptance_blockers"]
    assert "secret-managed-token" not in merged


def test_production_landing_env_runner_supports_local_infra_mcp_smoke_action(tmp_path: Path, monkeypatch) -> None:
    import scripts.production_landing_env_runner as runner

    env_path = tmp_path / "landing.env"
    env_path.write_text("", encoding="utf-8")

    class FakeCompleted:
        returncode = 0
        stdout = '{"status":"success","domain_count":3,"secret_plaintext_output":false}'
        stderr = ""

    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompleted()

    monkeypatch.setattr(runner, "_run_git", lambda args: "abc12345")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    summary = runner.build_production_landing_env_runner(
        action="local-infra-mcp-smoke",
        env_path=env_path,
        output_dir=tmp_path / "out",
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert "--domains" in captured["command"]
    assert "postgres,redis,external_mcp" in captured["command"]
    assert payload["child_summary"]["ready_domain_count"] == 3


def test_production_landing_env_runner_supports_local_business_smoke_action(tmp_path: Path, monkeypatch) -> None:
    import scripts.production_landing_env_runner as runner

    env_path = tmp_path / "landing.env"
    env_path.write_text("", encoding="utf-8")

    class FakeCompleted:
        returncode = 0
        stdout = '{"status":"success","business_system_connected":true,"business_read_executed":true,"secret_plaintext_output":false}'
        stderr = ""

    captured: dict[str, list[str]] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return FakeCompleted()

    monkeypatch.setattr(runner, "_run_git", lambda args: "abc12345")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    summary = runner.build_production_landing_env_runner(
        action="local-business-smoke",
        env_path=env_path,
        output_dir=tmp_path / "out",
    )
    payload = _payload(summary)

    assert summary["status"] == "success"
    assert any("production_landing_local_business_smoke.py" in part for part in captured["command"])
    assert payload["child_status"] == "success"


def test_production_landing_env_runner_passes_business_auth_header_env_to_business_smoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import scripts.production_landing_env_runner as runner

    env_path = tmp_path / "landing.env"
    env_path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
                "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
                "BUSINESS_SYSTEM_BASE_URL=https://business.example.test",
                "BUSINESS_SYSTEM_TOKEN=business-local-token-not-output",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=X-API-Key",
                "BUSINESS_SYSTEM_AUTH_SCHEME=",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=owner-secret-like-not-output",
                "BUSINESS_SYSTEM_SECURITY_REVIEWER=reviewer-secret-like-not-output",
                "BUSINESS_SYSTEM_OPERATIONS_OWNER=ops-secret-like-not-output",
                "BUSINESS_SYSTEM_DATA_OWNER=data-secret-like-not-output",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeCompleted:
        returncode = 0
        stdout = '{"status":"success","business_system_connected":true,"business_read_executed":true,"secret_plaintext_output":false}'
        stderr = ""

    captured: dict[str, str] = {}

    def fake_run(command, **kwargs):
        captured["command"] = " ".join(command)
        captured["auth_header"] = kwargs["env"]["BUSINESS_SYSTEM_AUTH_HEADER_NAME"]
        captured["auth_scheme"] = kwargs["env"]["BUSINESS_SYSTEM_AUTH_SCHEME"]
        captured["token"] = kwargs["env"]["BUSINESS_SYSTEM_TOKEN"]
        captured["business_owner"] = kwargs["env"]["BUSINESS_SYSTEM_BUSINESS_OWNER"]
        return FakeCompleted()

    monkeypatch.setattr(runner, "_run_git", lambda args: "abc12345")
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    summary = runner.build_production_landing_env_runner(
        action="business-smoke",
        env_path=env_path,
        output_dir=tmp_path / "out",
    )
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "success"
    assert "business_system_read_smoke.ps1" in captured["command"]
    assert "-UseExistingEnv" in captured["command"]
    assert "-EnvPath" in captured["command"]
    assert captured["auth_header"] == "X-API-Key"
    assert captured["auth_scheme"] == ""
    assert captured["token"] == "business-local-token-not-output"
    assert captured["business_owner"] == "owner-secret-like-not-output"
    assert "business-local-token-not-output" not in merged
    assert "owner-secret-like-not-output" not in merged
