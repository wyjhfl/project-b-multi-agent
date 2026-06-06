from __future__ import annotations

import json
from pathlib import Path

from scripts.business_system_production_readiness_brief import build_business_system_production_readiness_brief


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
    "BUSINESS_SYSTEM_BUSINESS_OWNER",
    "BUSINESS_SYSTEM_SECURITY_REVIEWER",
    "BUSINESS_SYSTEM_OPERATIONS_OWNER",
    "BUSINESS_SYSTEM_DATA_OWNER",
]


def _clear_env(monkeypatch) -> None:
    for key in BUSINESS_ENV_KEYS:
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


def _write_smoke_report(report_dir: Path, payload: dict, *, name: str = "001_business_system_read_smoke.json") -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / name
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-06T00:00:00+00:00",
                "status": "success",
                "business_system_connected": True,
                "business_read_executed": True,
                "business_write_executed": False,
                "business_data_written": False,
                "local_business_mock_used": False,
                "secret_plaintext_output": False,
                "missing_conditions": [],
                **payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_business_system_production_readiness_brief_defaults_to_needs_input(tmp_path: Path, monkeypatch) -> None:
    _clear_env(monkeypatch)

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=tmp_path / "missing_smoke",
    )
    payload = _payload(summary)

    assert payload["status"] == "needs_input"
    assert payload["read_only"] is True
    assert payload["latest_business_smoke"]["latest_report_present"] is False
    assert "owner:business_owner_missing" in payload["missing_conditions"]
    assert "evidence:business_system_real_read_smoke_not_executed" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["business_write_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["secret_plaintext_output"] is False


def test_business_system_production_readiness_brief_ready_with_real_read_smoke(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_ready_env(monkeypatch)
    smoke_dir = tmp_path / "smoke"
    _write_smoke_report(smoke_dir, {})

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=smoke_dir,
    )
    payload = _payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "ready"
    assert payload["missing_condition_count"] == 0
    assert payload["latest_business_smoke"]["business_read_executed"] is True
    assert payload["latest_business_smoke"]["local_business_mock_used"] is False
    assert payload["public_production_direct_launch"] == "No-Go"
    assert "sensitive-token-value" not in merged
    assert "https://business.example.test" not in merged


def test_business_system_production_readiness_brief_binds_explicit_current_smoke_over_stale_success(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_ready_env(monkeypatch)
    smoke_dir = tmp_path / "smoke"
    current_smoke = _write_smoke_report(
        smoke_dir,
        {
            "generated_at": "2026-06-06T00:00:00+00:00",
            "status": "skipped",
            "business_system_connected": False,
            "business_read_executed": False,
            "missing_conditions": ["cli:--execute_not_requested"],
        },
        name="001_business_system_read_smoke.json",
    )
    _write_smoke_report(
        smoke_dir,
        {
            "generated_at": "2026-06-06T01:00:00+00:00",
            "status": "success",
            "business_system_connected": True,
            "business_read_executed": True,
            "missing_conditions": [],
        },
        name="999_business_system_read_smoke.json",
    )

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=smoke_dir,
        business_smoke_json_path=current_smoke,
    )
    payload = _payload(summary)

    assert payload["status"] == "needs_input"
    assert payload["source_bound"] is True
    assert payload["latest_business_smoke"]["latest_json_path"] == str(current_smoke.resolve())
    assert payload["latest_business_smoke"]["source_bound"] is True
    assert payload["latest_business_smoke"]["source_selection"] == "explicit_json_path"
    assert payload["latest_business_smoke"]["business_read_executed"] is False
    assert "evidence:business_system_real_read_smoke_not_executed" in payload["missing_conditions"]


def test_business_system_production_readiness_brief_rejects_local_mock_smoke(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_ready_env(monkeypatch)
    smoke_dir = tmp_path / "smoke"
    _write_smoke_report(smoke_dir, {"local_business_mock_used": True})

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=smoke_dir,
    )
    payload = _payload(summary)

    assert payload["status"] == "needs_input"
    assert payload["latest_business_smoke"]["business_read_executed"] is True
    assert payload["latest_business_smoke"]["local_business_mock_used"] is True
    assert "evidence:local_business_mock_not_valid_for_real_production" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"


def test_business_system_production_readiness_brief_writes_valid_json_and_markdown(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=tmp_path / "missing_smoke",
    )
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["status"] == "needs_input"
    assert payload["required_inputs"][0]["description"] == "提供业务、数据、安全、运维四类负责人标识。"
    assert "# 业务系统生产只读接入 Readiness Brief" in markdown
    assert "�" not in markdown


def test_business_system_production_readiness_brief_blocks_write_or_secret_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_ready_env(monkeypatch)
    smoke_dir = tmp_path / "smoke"
    _write_smoke_report(
        smoke_dir,
        {
            "business_write_executed": True,
            "business_data_written": True,
            "secret_plaintext_output": True,
        },
    )

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=smoke_dir,
    )
    payload = _payload(summary)

    assert payload["status"] == "blocked"
    assert "boundary:business_write_detected" in payload["missing_conditions"]
    assert "boundary:secret_plaintext_output_detected" in payload["missing_conditions"]
    assert payload["public_production_direct_launch"] == "No-Go"


def test_business_system_production_readiness_brief_reports_secret_detection_flag(
    tmp_path: Path, monkeypatch
) -> None:
    _clear_env(monkeypatch)
    _set_ready_env(monkeypatch)
    smoke_dir = tmp_path / "smoke"
    _write_smoke_report(smoke_dir, {"note": "token=leaky-fixture"})

    summary = build_business_system_production_readiness_brief(
        output_dir=tmp_path / "out",
        business_smoke_report_dir=smoke_dir,
    )
    payload = _payload(summary)

    assert payload["status"] == "blocked"
    assert payload["secret_plaintext_output"] is True
    assert summary["secret_plaintext_output"] is True
    assert "boundary:secret_like_text_detected" in payload["missing_conditions"]
