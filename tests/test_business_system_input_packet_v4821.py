from __future__ import annotations

import json
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
    assert "业务系统真实接入输入准备包" in merged
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

    assert payload["status"] == "ready"
    assert payload["ready_for_real_read_smoke"] is True
    assert "sk-should-not-leak" not in merged
