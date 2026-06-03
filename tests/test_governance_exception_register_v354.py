from __future__ import annotations

import json
from pathlib import Path

from scripts.governance_exception_register import build_governance_exception_register


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_governance_exception_register_generates_default_skipped_register(tmp_path: Path) -> None:
    summary = build_governance_exception_register(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["version"] == "3.6.0"
    assert payload["mode"] == "fake_offline_default"
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["service_started"] is False
    assert payload["auto_approved"] is False
    assert payload["exception_count"] == 5
    assert {item["status"] for item in payload["exception_register"]} == {"skipped"}
    assert Path(summary["markdown_path"]).exists()


def test_governance_exception_register_uses_source_metadata_without_approval(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    governance = tmp_path / "governance.json"
    incident = tmp_path / "incident.json"
    scoring = tmp_path / "scoring.json"
    integration = tmp_path / "integration.json"
    for path, status in [
        (config, "success"),
        (governance, "success"),
        (incident, "partial"),
        (scoring, "success"),
        (integration, "skipped"),
    ]:
        _write_json(
            path,
            {
                "status": status,
                "version": "3.6.0",
                "mode": "fake_offline_default",
                "read_only": True,
                "real_llm_executed": False,
                "missing_conditions": [f"{path.stem}:manual_condition"],
                "warnings": [f"{path.stem}:warning"],
                "recommended_actions": [f"{path.stem}:manual_review"],
            },
        )

    summary = build_governance_exception_register(
        output_dir=tmp_path / "out",
        config_drift=config,
        governance_policy=governance,
        incident_report=incident,
        operator_scoring=scoring,
        controlled_integration=integration,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert {item["status"] for item in payload["exception_register"]} == {"pending_review"}
    assert {item["approval_state"] for item in payload["exception_register"]} == {"not_approved"}
    assert payload["auto_approved"] is False
    assert "integration:manual_condition" in payload["missing_conditions"]
    assert "controlled_integration:source_status_skipped" in payload["missing_conditions"]


def test_governance_exception_register_blocks_secret_like_source(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    key_value = "sk-" + "should-not-leak"
    db_url = "postgresql" + "://" + "demo:secret@localhost/db"
    _write_json(
        config,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": False,
            "api_key": key_value,
            "DATABASE_URL": db_url,
            "missing_conditions": [db_url],
        },
    )

    summary = build_governance_exception_register(output_dir=tmp_path / "out", config_drift=config)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    config_exception = next(item for item in payload["exception_register"] if item["source"] == "config_drift")
    assert config_exception["status"] == "blocked"
    assert "config_drift:secret_like_value_detected" in payload["missing_conditions"]
    assert key_value not in merged
    assert ("postgresql" + "://demo:secret@") not in merged


def test_governance_exception_register_blocks_unexpected_external_execution(tmp_path: Path) -> None:
    integration = tmp_path / "integration.json"
    _write_json(
        integration,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": True,
            "external_mcp_connected": True,
            "auto_approved": True,
        },
    )

    summary = build_governance_exception_register(output_dir=tmp_path / "out", controlled_integration=integration)
    payload = _read_payload(summary)
    integration_exception = next(item for item in payload["exception_register"] if item["source"] == "controlled_integration")

    assert summary["status"] == "blocked"
    assert integration_exception["status"] == "blocked"
    assert "controlled_integration:real_llm_executed_unexpected" in payload["missing_conditions"]
    assert "controlled_integration:external_mcp_connected_unexpected" in payload["missing_conditions"]
    assert "controlled_integration:auto_approved_unexpected" in payload["missing_conditions"]
    assert payload["real_llm_executed"] is False
    assert payload["external_mcp_connected"] is False
    assert payload["auto_approved"] is False


def test_governance_exception_register_preserves_required_fields(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    _write_json(config, {"status": "success", "read_only": True, "real_llm_executed": False, "warnings": ["needs_owner"]})

    summary = build_governance_exception_register(output_dir=tmp_path / "out", config_drift=config)
    payload = _read_payload(summary)
    exception = next(item for item in payload["exception_register"] if item["source"] == "config_drift")

    assert {
        "exception_id",
        "source",
        "risk_description",
        "scope",
        "owner",
        "expires_at",
        "compensating_controls",
        "review_evidence",
        "status",
        "next_actions",
        "approval_state",
    } <= set(exception)
    assert exception["owner"] == "manual_owner_required"
    assert exception["expires_at"] == "manual_expiry_required"
