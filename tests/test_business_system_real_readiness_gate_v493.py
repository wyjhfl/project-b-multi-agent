from __future__ import annotations

import json
from pathlib import Path

from scripts.business_system_real_readiness_gate import build_business_system_real_readiness_gate


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _write_env(path: Path, *, system_name: str = "real_crm", token: str = "secret-managed-token") -> None:
    path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                f"BUSINESS_SYSTEM_NAME={system_name}",
                "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
                "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
                "BUSINESS_SYSTEM_BASE_URL=https://business.example.test",
                f"BUSINESS_SYSTEM_TOKEN={token}",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
                "BUSINESS_SYSTEM_TIMEOUT_SECONDS=5",
                "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=operator-staff-id",
                "BUSINESS_SYSTEM_SECURITY_REVIEWER=operator-staff-id",
                "BUSINESS_SYSTEM_OPERATIONS_OWNER=operator-staff-id",
                "BUSINESS_SYSTEM_DATA_OWNER=operator-staff-id",
            ]
        ),
        encoding="utf-8",
    )


def test_business_system_real_readiness_gate_ready_for_real_env(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    _write_env(env_path)

    summary = build_business_system_real_readiness_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "ready"
    assert summary["ready_for_real_read_smoke"] is True
    assert summary["local_mock_configured"] is False
    assert payload["missing_conditions"] == []
    assert payload["key_statuses"]["BUSINESS_SYSTEM_TOKEN"]["present"] is True
    assert payload["key_statuses"]["BUSINESS_SYSTEM_TOKEN"]["secret_value_key"] is True
    assert payload["recommended_commands"][0].endswith("scripts\\business_system_read_smoke.ps1 -UseExistingEnv")
    assert "BusinessOwner WYJ" not in "\n".join(payload["recommended_commands"])
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["public_production_direct_launch"] == "No-Go"


def test_business_system_real_readiness_gate_markdown_has_no_mojibake(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    _write_env(env_path)

    summary = build_business_system_real_readiness_gate(env_path=env_path, output_dir=tmp_path / "out")
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    for marker in ("鐢", "鍙", "绯", "鎺", "杈", "缂", "銆", "�"):
        assert marker not in markdown
    assert "业务系统真实只读接入门禁" in markdown
    assert "边界" in markdown


def test_business_system_real_readiness_gate_blocks_local_mock_env(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    _write_env(env_path, system_name="local_business_read_mock")

    summary = build_business_system_real_readiness_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert summary["ready_for_real_read_smoke"] is False
    assert summary["local_mock_configured"] is True
    assert "business_system:local_mock_configured" in payload["missing_conditions"]
    assert payload["secret_plaintext_output"] is False


def test_business_system_real_readiness_gate_blocks_demo_business_env(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    _write_env(env_path, system_name="demo_business_system")

    summary = build_business_system_real_readiness_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert summary["ready_for_real_read_smoke"] is False
    assert payload["demo_business_system_configured"] is True
    assert "business_system:demo_business_system_configured" in payload["missing_conditions"]
    assert payload["secret_plaintext_output"] is False


def test_business_system_real_readiness_gate_detects_unsafe_write_config(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    _write_env(env_path)
    text = env_path.read_text(encoding="utf-8")
    text = text.replace("BUSINESS_INTEGRATION_WRITE_ENABLED=false", "BUSINESS_INTEGRATION_WRITE_ENABLED=true")
    text = text.replace("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=", "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=business_write")
    env_path.write_text(text, encoding="utf-8")

    summary = build_business_system_real_readiness_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert "env:BUSINESS_INTEGRATION_WRITE_ENABLED_unexpected_value" in payload["missing_conditions"]
    assert "env:BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST_unexpected_value" in payload["missing_conditions"]
    assert payload["ready_for_real_read_smoke"] is False


def test_business_system_real_readiness_gate_does_not_write_secret_values(tmp_path: Path) -> None:
    env_path = tmp_path / "landing.env"
    _write_env(env_path, token="token-value-that-must-not-appear")

    summary = build_business_system_real_readiness_gate(env_path=env_path, output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )
    payload = _payload(summary)

    assert payload["key_statuses"]["BUSINESS_SYSTEM_TOKEN"]["present"] is True
    assert "token-value-that-must-not-appear" not in merged
    assert "https://business.example.test" not in merged
    assert payload["secret_plaintext_output"] is False


def test_business_system_real_readiness_gate_uses_process_secret_over_placeholder(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / "landing.env"
    _write_env(env_path, token="<secret-managed-token>")
    text = env_path.read_text(encoding="utf-8").replace(
        "BUSINESS_SYSTEM_BASE_URL=https://business.example.test",
        "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
    )
    env_path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", "https://process.example.test")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", "process-token-value")

    summary = build_business_system_real_readiness_gate(env_path=env_path, output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "ready"
    assert payload["key_statuses"]["BUSINESS_SYSTEM_BASE_URL"]["source"] == "process_env_over_env_file_placeholder"
    assert payload["key_statuses"]["BUSINESS_SYSTEM_TOKEN"]["source"] == "process_env_over_env_file_placeholder"
    assert "process-token-value" not in merged
    assert "https://process.example.test" not in merged
