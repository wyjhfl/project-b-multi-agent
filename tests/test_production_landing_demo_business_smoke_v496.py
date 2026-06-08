from __future__ import annotations

import json
from pathlib import Path

from scripts.business_system_landing_execution_pack import build_business_system_landing_execution_pack
from scripts.business_system_production_readiness_brief import build_business_system_production_readiness_brief
from scripts.production_landing_demo_business_smoke import build_production_landing_demo_business_smoke


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_demo_business_smoke_runs_read_only_service_and_marks_demo_boundary(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / "landing.env"
    env_path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                "BUSINESS_SYSTEM_NAME=demo_business_system",
                "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
                "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
                "BUSINESS_SYSTEM_BASE_URL=http://127.0.0.1:8876",
                "BUSINESS_SYSTEM_TOKEN=demo-business-read-token",
                "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
                "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
                "BUSINESS_SYSTEM_TIMEOUT_SECONDS=5",
                "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
                "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
                "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("BUSINESS_SYSTEM_TOKEN", raising=False)

    summary = build_production_landing_demo_business_smoke(output_dir=tmp_path / "out", env_path=env_path)
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert summary["status"] == "success"
    assert summary["demo_server_ready"] is True
    assert summary["demo_business_system_used"] is True
    assert summary["local_business_mock_used"] is False
    assert payload["business_system_connected"] is True
    assert payload["business_read_executed"] is True
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["demo_business_system_used"] is True
    assert payload["local_business_mock_used"] is False
    assert payload["secret_plaintext_output"] is False
    assert "demo-business-read-token" not in merged


def test_readiness_brief_rejects_demo_business_smoke_for_real_production(tmp_path: Path, monkeypatch) -> None:
    for key in [
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
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BUSINESS_INTEGRATION_ENABLED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_READ_ONLY", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_WRITE_ENABLED", "false")
    monkeypatch.setenv("BUSINESS_INTEGRATION_APPROVAL_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_INTEGRATION_AUDIT_REQUIRED", "true")
    monkeypatch.setenv("BUSINESS_SYSTEM_NAME", "demo_business_system")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL_ENV", "BUSINESS_SYSTEM_BASE_URL")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN_ENV", "BUSINESS_SYSTEM_TOKEN")
    monkeypatch.setenv("BUSINESS_SYSTEM_BASE_URL", "http://127.0.0.1:8876")
    monkeypatch.setenv("BUSINESS_SYSTEM_TOKEN", "demo-business-read-token")
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
    smoke_dir = tmp_path / "smoke"
    _write_json(
        smoke_dir / "001_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-08T00:00:00+00:00",
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "demo_business_system_used": True,
            "secret_plaintext_output": False,
            "missing_conditions": [],
        },
    )

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=smoke_dir,
    )
    payload = _payload(summary)

    assert payload["status"] == "needs_input"
    assert payload["latest_business_smoke"]["business_read_executed"] is True
    assert payload["latest_business_smoke"]["demo_business_system_used"] is True
    assert "evidence:demo_business_system_not_valid_for_real_production" in payload["missing_conditions"]


def test_landing_execution_pack_rejects_demo_business_smoke_as_real_completion(tmp_path: Path) -> None:
    input_path = _write_json(
        tmp_path / "input" / "001_business_system_input_packet.json",
        {
            "generated_at": "2026-06-08T00:00:00+00:00",
            "status": "ready",
            "ready_for_real_read_smoke": True,
            "missing_conditions": [],
            "manual_input_checklist": [],
        },
    )
    readiness_path = _write_json(
        tmp_path / "readiness" / "001_business_system_production_readiness.json",
        {
            "generated_at": "2026-06-08T00:00:01+00:00",
            "status": "needs_input",
            "missing_conditions": ["evidence:demo_business_system_not_valid_for_real_production"],
            "required_inputs": [],
        },
    )
    smoke_path = _write_json(
        tmp_path / "smoke" / "001_business_system_read_smoke.json",
        {
            "generated_at": "2026-06-08T00:00:02+00:00",
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "business_write_executed": False,
            "business_data_written": False,
            "local_business_mock_used": False,
            "demo_business_system_used": True,
            "secret_plaintext_output": False,
            "missing_conditions": [],
        },
    )

    summary = build_business_system_landing_execution_pack(
        output_dir=tmp_path / "out",
        report_dirs={
            "business_system_input_packet": tmp_path / "input",
            "business_system_production_readiness": tmp_path / "readiness",
            "business_system_read_smoke": tmp_path / "smoke",
        },
        source_json_paths={
            "business_system_input_packet": input_path,
            "business_system_production_readiness": readiness_path,
            "business_system_read_smoke": smoke_path,
        },
    )
    payload = _payload(summary)

    assert payload["status"] == "needs_input"
    assert payload["real_read_smoke_complete"] is False
    assert payload["business_system_read_smoke"]["demo_business_system_used"] is True
    assert "evidence:demo_business_system_not_valid_for_real_production" in payload["missing_conditions"]
