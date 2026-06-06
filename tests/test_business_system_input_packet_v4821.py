from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.business_system_input_packet import build_business_system_input_packet


BUSINESS_INPUT_ENV_KEYS = [
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
    "BUSINESS_SYSTEM_BUSINESS_OWNER",
    "BUSINESS_SYSTEM_SECURITY_REVIEWER",
    "BUSINESS_SYSTEM_OPERATIONS_OWNER",
    "BUSINESS_SYSTEM_DATA_OWNER",
]


def _clear_env(monkeypatch) -> None:
    for key in BUSINESS_INPUT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _set_ready_env(monkeypatch) -> None:
    monkeypatch.setenv("BUSINESS_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_READ_ONLY", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_WRITE_ENABLED", "false")
    monkeypatch.setenv("BUSINESS_INTEGRATION_APPROVAL_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_AUDIT_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_SYSTEM_NAME", "crm")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_BASE_URL")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN_ENV", "BUSINESS_SYSTEM_TOKEN")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", "https://business.example.test")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", "sensitive-token-value")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOOL_ALLOWLIST", "business_read_probe")
    monkeypatch.setenv("BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST", "")
    monkeypatch.setenv("BUSINESS_SYSTEM_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("BUSINESS_SYSTEM_READ_PROBE_PATH", "/health")
    monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_HEADER_NAME", "Authorization")
    monkeypatch.setenv("BUSINESS_SYSTEM_AUTH_SCHEME", "Bearer")
    monkeypatch.setenv("BUSINESS_SYSTEM_BUSINESS_OWNER", "wyj")
    monkeypatch.setenv("BUSINESS_SYSTEM_SECURITY_REVIEWER", "wyj")
    monkeypatch.setenv("BUSINESS_SYSTEM_OPERATIONS_OWNER", "wyj")
    monkeypatch.setenv("BUSINESS_SYSTEM_DATA_OWNER", "wyj")


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_business_system_input_packet_defaults_to_needs_input(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)

    summary = build_business_system_input_packet(output_dir=tmp_path / "out")
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert payload["ready_for_real_read_smoke"] is False
    assert payload["owner_inputs_present"] == {
        "business_owner": False,
        "security_reviewer": False,
        "operations_owner": False,
        "data_owner": False,
    }
    assert "owner:business_owner_missing" in payload["missing_conditions"]
    assert "env:BUSINESS_SYSTEM_BASE_URL_ENV_missing" in payload["missing_conditions"]
    assert "env:BUSINESS_SYSTEM_TOKEN_ENV_missing" in payload["missing_conditions"]
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert payload["public_production_direct_launch"] == "No-Go"
    assert "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>" in payload["local_env_template_lines"]
    assert "BUSINESS_INTEGRATION_WRITE_ENABLED=false" in payload["local_env_template_lines"]
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in payload["local_env_template_lines"]
    assert payload["manual_input_checklist"][0]["id"] == "owners"


def test_business_system_input_packet_ready_without_secret_leak(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_ready_env(monkeypatch)

    summary = build_business_system_input_packet(output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "ready"
    assert payload["ready_for_real_read_smoke"] is True
    assert payload["missing_condition_count"] == 0
    assert all(payload["owner_inputs_present"].values())
    assert "sensitive-token-value" not in merged
    assert "https://business.example.test" not in merged
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in merged
    assert "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>" in merged
    assert "只读 token 仅进入当前进程环境" in merged
    assert "业务系统真实接入输入准备包" in merged
    assert "business_system_read_smoke.ps1 -PreflightOnly -EnvPath local\\production_landing.staging.env" in merged
    assert "business_system_read_smoke.ps1 -EnvPath local\\production_landing.staging.env" in merged
    assert "scripts\\business_system_landing_resume.ps1 -UseExistingEnv" in merged
    assert "public_production_direct_launch" in merged
    assert "No-Go" in merged


def test_business_system_input_packet_does_not_emit_owner_values(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)
    _set_ready_env(monkeypatch)
    monkeypatch.setenv("BUSINESS_SYSTEM_BUSINESS_OWNER", "token=sk-should-not-leak")

    summary = build_business_system_input_packet(output_dir=tmp_path / "out")
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "blocked"
    assert payload["ready_for_real_read_smoke"] is False
    assert payload["secret_plaintext_output"] is True
    assert summary["secret_plaintext_output"] is True
    assert "boundary:secret_like_text_detected" in payload["missing_conditions"]
    assert "owner:business_owner_secret_like" in payload["missing_conditions"]
    assert "sk-should-not-leak" not in merged


def test_business_system_input_packet_loads_safe_env_path_and_skips_secret_keys(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    env_path = tmp_path / "landing.env"
    env_path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                "BUSINESS_SYSTEM_NAME=real_crm",
                "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
                "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
                "BUSINESS_SYSTEM_BASE_URL=https://must-not-be-loaded.example.test",
                "BUSINESS_SYSTEM_TOKEN=must-not-be-loaded-token",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
                "BUSINESS_SYSTEM_TIMEOUT_SECONDS=5",
                "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=WYJ",
                "BUSINESS_SYSTEM_SECURITY_REVIEWER=WYJ",
                "BUSINESS_SYSTEM_OPERATIONS_OWNER=WYJ",
                "BUSINESS_SYSTEM_DATA_OWNER=WYJ",
                "UNRELATED_SECRET=should-be-ignored",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", "https://process.example.test")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", "process-token")

    summary = build_business_system_input_packet(output_dir=tmp_path / "out", env_path=env_path)
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "ready"
    assert payload["ready_for_real_read_smoke"] is True
    assert payload["env_file_present"] is True
    assert "BUSINESS_SYSTEM_NAME" in payload["env_path_loaded_keys"]
    assert "BUSINESS_SYSTEM_BASE_URL" in payload["env_path_secret_keys_skipped"]
    assert "BUSINESS_SYSTEM_TOKEN" in payload["env_path_secret_keys_skipped"]
    assert "UNRELATED_SECRET" in payload["env_path_unknown_keys_ignored"]
    assert "must-not-be-loaded" not in merged
    assert "process-token" not in merged
    assert "https://process.example.test" not in merged
    assert "business_system_input_packet.py --env-path local\\production_landing.staging.env" in merged
    assert os.environ.get("BUSINESS_SYSTEM_NAME") is None


def test_business_system_input_packet_treats_template_placeholders_as_missing(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    env_path = tmp_path / "landing.env"
    env_path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                "BUSINESS_SYSTEM_NAME=<system-name>",
                "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
                "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
                "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
                "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>",
                "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>",
                "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>",
                "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", "<secret-managed-url>")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", "<secret-managed-token>")

    summary = build_business_system_input_packet(output_dir=tmp_path / "out", env_path=env_path)
    payload = _payload(summary)

    assert summary["status"] == "needs_input"
    assert payload["ready_for_real_read_smoke"] is False
    assert "owner:business_owner_missing" in payload["missing_conditions"]
    assert "env_target:BUSINESS_SYSTEM_BASE_URL_missing" in payload["missing_conditions"]
    assert "env_target:BUSINESS_SYSTEM_TOKEN_missing" in payload["missing_conditions"]
