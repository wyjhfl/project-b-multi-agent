from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_local_business_smoke import build_production_landing_local_business_smoke


def test_local_business_smoke_runs_embedded_mock_and_delegates_smoke(tmp_path, monkeypatch) -> None:
    import scripts.production_landing_local_business_smoke as smoke
    import os

    captured = {}

    def fake_business_smoke(*, output_dir, execute, local_business_mock_used):
        captured["output_dir"] = output_dir
        captured["execute"] = execute
        captured["local_business_mock_used"] = local_business_mock_used
        captured["auth_header"] = os.environ.get("BUSINESS_SYSTEM_AUTH_HEADER_NAME")
        captured["auth_scheme"] = os.environ.get("BUSINESS_SYSTEM_AUTH_SCHEME")
        return {
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": local_business_mock_used,
            "secret_plaintext_output": False,
        }

    monkeypatch.setattr(smoke, "build_business_system_read_smoke", fake_business_smoke)

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
                "BUSINESS_SYSTEM_BASE_URL=http://127.0.0.1:8765",
                "BUSINESS_SYSTEM_TOKEN=local-business-read-token",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=X-API-Key",
                "BUSINESS_SYSTEM_AUTH_SCHEME=",
            ]
        ),
        encoding="utf-8",
    )

    summary = build_production_landing_local_business_smoke(output_dir=tmp_path / "out", env_path=env_path)

    assert summary["status"] == "success"
    assert summary["mock_server_ready"] is True
    assert summary["local_business_mock_used"] is True
    assert summary["env_file_present"] is True
    assert summary["env_key_count"] == 12
    assert captured["execute"] is True
    assert captured["local_business_mock_used"] is True
    assert captured["auth_header"] == "X-API-Key"
    assert captured["auth_scheme"] == ""
    assert summary["business_system_connected"] is True
    assert summary["secret_plaintext_output"] is False


def test_local_business_smoke_restores_process_environment(tmp_path, monkeypatch) -> None:
    import os

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
                "BUSINESS_SYSTEM_BASE_URL=http://127.0.0.1:8765",
                "BUSINESS_SYSTEM_TOKEN=local-business-read-token",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("BUSINESS_SYSTEM_TOKEN", raising=False)

    summary = build_production_landing_local_business_smoke(output_dir=tmp_path / "out", env_path=env_path)

    assert summary["status"] == "success"
    assert os.environ.get("BUSINESS_SYSTEM_TOKEN") is None


def test_local_business_smoke_persists_mock_flag_into_report(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / "landing.env"
    env_path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                "BUSINESS_SYSTEM_NAME=local_fixture_crm",
                "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
                "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
                "BUSINESS_SYSTEM_BASE_URL=http://127.0.0.1:8765",
                "BUSINESS_SYSTEM_TOKEN=local-business-read-token",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
                "BUSINESS_SYSTEM_TIMEOUT_SECONDS=5",
                "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("BUSINESS_SYSTEM_TOKEN", raising=False)

    summary = build_production_landing_local_business_smoke(output_dir=tmp_path / "out", env_path=env_path)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "success"
    assert summary["local_business_mock_used"] is True
    assert payload["local_business_mock_used"] is True
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert "- local_business_mock_used: True" in markdown
