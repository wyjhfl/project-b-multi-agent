from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.harness.gateway.tool_gateway import ToolGateway
from app.integrations.business_system import load_business_system_config, register_business_system_tools
from scripts.business_system_read_smoke import build_business_system_env_template, build_business_system_read_smoke


BUSINESS_ENV_KEYS = [
    "BUSINESS_INTEGRATION_ENABLED",
    "BUSINESS_INTEGRATION_READ_ONLY",
    "BUSINESS_INTEGRATION_WRITE_ENABLED",
    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED",
    "BUSINESS_INTEGRATION_AUDIT_REQUIRED",
    "BUSINESS_SYSTEM_NAME",
    "BUSINESS_SYSTEM_BASE_URL_ENV",
    "BUSINESS_SYSTEM_TOKEN_ENV",
    "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN",
    "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_TIMEOUT_SECONDS",
    "BUSINESS_SYSTEM_READ_PROBE_PATH",
    "BUSINESS_SYSTEM_AUTH_HEADER_NAME",
    "BUSINESS_SYSTEM_AUTH_SCHEME",
    "CI",
    "GITHUB_ACTIONS",
    "TF_BUILD",
    "BUILD_BUILDID",
    "JENKINS_URL",
]


def _clear_env(monkeypatch) -> None:
    for key in BUSINESS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


class _Handler(BaseHTTPRequestHandler):
    token_seen = ""
    custom_token_seen = ""
    response_status = 200

    def do_GET(self):  # noqa: N802
        _Handler.token_seen = self.headers.get("authorization", "")
        _Handler.custom_token_seen = self.headers.get("x-api-key", "")
        self.send_response(_Handler.response_status)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true, "system": "fixture"}')

    def log_message(self, format, *args):  # noqa: A002
        return


class _FixtureServer:
    def __init__(self, host: str = "127.0.0.1") -> None:
        self.host = host

    def __enter__(self):
        _Handler.token_seen = ""
        _Handler.custom_token_seen = ""
        _Handler.response_status = 200
        self.server = ThreadingHTTPServer((self.host, 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=2)


def _set_opt_in(monkeypatch, base_url: str, token: str = "business-token-sensitive") -> None:
    monkeypatch.setenv("BUSINESS_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_READ_ONLY", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_WRITE_ENABLED", "false")
    monkeypatch.setenv("BUSINESS_INTEGRATION_APPROVAL_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_AUDIT_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_SYSTEM_NAME", "fixture_crm")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_BASE_URL")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN_ENV", "BUSINESS_SYSTEM_TOKEN")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", base_url)
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", token)
    monkeypatch.setenv("BUSINESS_SYSTEM_TOOL_ALLOWLIST", "business_read_probe")
    monkeypatch.setenv("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST", "")
    monkeypatch.setenv("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("BUSINESS_SYSTEM_READ_PROBE_PATH", "/health")
    monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_HEADER_NAME", "Authorization")
    monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_SCHEME", "Bearer")


def test_business_system_read_smoke_default_skipped(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)

    summary = build_business_system_read_smoke(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["status"] == "skipped"
    assert payload["read_only"] is True
    assert payload["execution_requested"] is False
    assert payload["env_profile"]["execution_requested"] is False
    assert payload["env_profile"]["ready_for_execute"] is False
    assert payload["env_profile"]["local_business_mock_used"] is False
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in payload["env_profile"]["required_env"]
    assert payload["env_profile"]["auth_mode"] == "bearer"
    assert payload["env_profile"]["public_production_gap"] is True
    assert payload["env_profile"]["safe_commands"]["interactive_powershell"].endswith(
        "scripts\\business_system_read_smoke.ps1"
    )
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["local_business_mock_used"] is False
    assert summary["local_business_mock_used"] is False
    assert payload["secret_plaintext_output"] is False
    assert "业务系统只读 Smoke 报告" in markdown
    assert "鍙" not in markdown
    assert "�" not in markdown


def test_business_system_env_template_is_read_only_and_placeholder_only(tmp_path: Path) -> None:
    template = tmp_path / "business.env.template"

    summary = build_business_system_env_template(output_path=template)
    text = template.read_text(encoding="utf-8")

    assert summary["status"] == "success"
    assert summary["business_write_enabled"] is False
    assert "BUSINESS_INTEGRATION_WRITE_ENABLED=false" in text
    assert "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe" in text
    assert "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=" in text
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization" in text
    assert "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer" in text
    assert "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>" in text
    assert "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>" in text
    assert "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>" in text
    assert "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>" in text
    assert "sk-" not in text
    assert "bearer " not in text.lower()


def test_business_system_read_smoke_execute_blocks_when_env_missing(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)

    summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert payload["read_only"] is True
    assert payload["execution_requested"] is True
    assert payload["env_profile"]["execution_requested"] is True
    assert payload["env_profile"]["ready_for_execute"] is False
    assert "opt_in:BUSINESS_INTEGRATION_ENABLED_not_enabled" in payload["missing_conditions"]
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False


def test_business_system_read_smoke_execute_blocks_unsafe_write_or_missing_control_env(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setenv("BUSINESS_INTEGRATION_WRITE_ENABLED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_APPROVAL_REQUIRED", "false")
    monkeypatch.setenv("BUSINESS_INTEGRATION_AUDIT_REQUIRED", "false")
    monkeypatch.setenv("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST", "business_write_probe")

    summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert "opt_in:BUSINESS_INTEGRATION_WRITE_ENABLED_must_be_false" in payload["missing_conditions"]
    assert "opt_in:BUSINESS_INTEGRATION_APPROVAL_REQUIRED_not_enabled" in payload["missing_conditions"]
    assert "opt_in:BUSINESS_INTEGRATION_AUDIT_REQUIRED_not_enabled" in payload["missing_conditions"]
    assert "env:BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST_must_be_empty" in payload["missing_conditions"]
    assert payload["business_read_executed"] is False
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False


def test_business_system_registers_read_probe_only_when_allowlisted(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")
    gateway = ToolGateway()

    specs = register_business_system_tools(gateway, load_business_system_config())

    assert [spec.tool_name for spec in specs] == ["business_read_probe"]
    assert gateway.get_tool("business_read_probe") is not None


def test_business_system_read_probe_rejects_unsafe_base_url(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "https://user:pass@business.example.test#fragment")
    gateway = ToolGateway()
    register_business_system_tools(gateway, load_business_system_config())

    record = gateway.call("business_read_probe", {})

    assert record.success is False
    assert record.result["error"] == "business_system_base_url_invalid"


def test_business_system_read_probe_rejects_unsafe_auth_header_name(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_HEADER_NAME", "Authorization: X-Bad")
    gateway = ToolGateway()
    register_business_system_tools(gateway, load_business_system_config())

    record = gateway.call("business_read_probe", {})

    assert record.success is False
    assert record.result["error"] == "business_system_auth_header_name_invalid"


def test_business_system_read_probe_rejects_unsafe_auth_scheme(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_SCHEME", "Bearer\r\nX-Bad: yes")
    gateway = ToolGateway()
    register_business_system_tools(gateway, load_business_system_config())

    record = gateway.call("business_read_probe", {})

    assert record.success is False
    assert record.result["error"] == "business_system_auth_scheme_invalid"


def test_business_system_read_probe_rejects_token_with_control_chars(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1", token="safe-token\r\nX-Bad: yes")
    gateway = ToolGateway()
    register_business_system_tools(gateway, load_business_system_config())

    record = gateway.call("business_read_probe", {})

    assert record.success is False
    assert record.result["error"] == "business_system_token_invalid"


def test_business_system_read_probe_rejects_unsafe_probe_path(monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")
    gateway = ToolGateway()
    register_business_system_tools(gateway, load_business_system_config())

    relative = gateway.call("business_read_probe", {"path": "health"})
    protocol_relative = gateway.call("business_read_probe", {"path": "//evil.example.test/health"})
    control_char = gateway.call("business_read_probe", {"path": "/health\r\nX-Bad: yes"})

    assert relative.success is False
    assert relative.result["error"] == "business_probe_path_must_be_absolute"
    assert protocol_relative.success is False
    assert protocol_relative.result["error"] == "business_probe_path_must_be_absolute"
    assert control_char.success is False
    assert control_char.result["error"] == "business_probe_path_must_be_absolute"


def test_business_system_read_smoke_execute_failure_does_not_mark_read_executed(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")

    summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "failed"
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False
    assert payload["smoke"]["gateway_call_success"] is False
    assert payload["smoke"]["error"] == "business_read_probe_failed"


def test_business_system_read_smoke_blocks_real_execute_in_automation(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setenv("CI", "true")

    summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert "automation:real_business_read_smoke_blocked" in payload["missing_conditions"]
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False


def test_business_system_read_smoke_allows_explicit_local_mock_in_automation(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    with _FixtureServer() as server:
        _set_opt_in(monkeypatch, server.url)
        monkeypatch.setenv("CI", "true")

        summary = build_business_system_read_smoke(
            output_dir=tmp_path / "out",
            execute=True,
            local_business_mock_used=True,
        )

    payload = _read_payload(summary)

    assert payload["status"] == "success"
    assert payload["business_read_executed"] is True
    assert payload["local_business_mock_used"] is True
    assert "automation:real_business_read_smoke_blocked" not in payload["missing_conditions"]


def test_business_system_read_smoke_execute_fails_on_non_2xx_without_marking_read(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    with _FixtureServer() as server:
        _Handler.response_status = 503
        _set_opt_in(monkeypatch, server.url)

        summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)

    payload = _read_payload(summary)

    assert payload["status"] == "failed"
    assert payload["business_system_connected"] is False
    assert payload["business_read_executed"] is False
    assert payload["smoke"]["gateway_call_success"] is False
    assert payload["smoke"]["error"] == "business_read_probe_failed"


def test_business_system_read_smoke_supports_custom_auth_header_without_secret_leak(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    with _FixtureServer() as server:
        _set_opt_in(monkeypatch, server.url)
        monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_HEADER_NAME", "X-API-Key")
        monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_SCHEME", "")

        summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)

    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "success"
    assert _Handler.custom_token_seen == "business-token-sensitive"
    assert _Handler.token_seen == ""
    assert payload["config"]["auth_header_name"] == "X-API-Key"
    assert payload["config"]["auth_scheme_configured"] is False
    assert "business-token-sensitive" not in merged


def test_business_system_read_smoke_execute_success_without_secret_leak(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    with _FixtureServer() as server:
        _set_opt_in(monkeypatch, server.url)

        summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)

    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "success"
    assert payload["read_only"] is True
    assert payload["execution_requested"] is True
    assert payload["env_profile"]["ready_for_execute"] is True
    assert payload["env_profile"]["auth_mode"] == "bearer"
    assert payload["env_profile"]["local_business_mock_used"] is False
    assert payload["env_profile"]["public_production_gap"] is False
    assert payload["env_profile"]["present"]["write_tool_allowlist_empty"] is True
    assert payload["business_system_connected"] is True
    assert payload["business_read_executed"] is True
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["local_business_mock_used"] is False
    assert _Handler.token_seen == "Bearer business-token-sensitive"
    assert "business-token-sensitive" not in merged
    assert "Bearer " not in merged
    assert server.url not in merged
    assert "<secret-managed-token>" in merged
    assert payload["secret_plaintext_output"] is False


def test_business_system_read_smoke_marks_only_explicit_local_mock_as_public_gap(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    with _FixtureServer() as server:
        _set_opt_in(monkeypatch, server.url)
        monkeypatch.setenv("BUSINESS_SYSTEM_NAME", "local_business_read_mock")

        summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)

    payload = _read_payload(summary)

    assert payload["status"] == "success"
    assert payload["business_read_executed"] is True
    assert payload["local_business_mock_used"] is True
    assert payload["env_profile"]["local_business_mock_used"] is True
    assert payload["env_profile"]["public_production_gap"] is True


def test_business_system_read_smoke_does_not_treat_localhost_tunnel_as_mock(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    with _FixtureServer(host="localhost") as server:
        _set_opt_in(monkeypatch, server.url)

        summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)

    payload = _read_payload(summary)

    assert payload["status"] == "success"
    assert payload["business_read_executed"] is True
    assert payload["local_business_mock_used"] is False
    assert payload["env_profile"]["local_business_mock_used"] is False
    assert payload["env_profile"]["public_production_gap"] is False


def test_business_system_read_smoke_reports_secret_detection_flag(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_opt_in(monkeypatch, "http://127.0.0.1:1")
    monkeypatch.setenv("BUSINESS_SYSTEM_NAME", "token=leaky-fixture")

    summary = build_business_system_read_smoke(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert summary["secret_plaintext_output"] is True
    assert "output:secret_like_text_detected" in payload["missing_conditions"]
