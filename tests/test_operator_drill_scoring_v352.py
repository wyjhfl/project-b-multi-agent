from __future__ import annotations

import json
from pathlib import Path

from scripts.operator_drill_scoring import build_operator_drill_scoring


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_operator_drill_scoring_all_sources_success(tmp_path: Path) -> None:
    incident = tmp_path / "incident.json"
    handoff = tmp_path / "handoff.json"
    readiness = tmp_path / "readiness.json"
    comparison = tmp_path / "comparison.json"
    _write_json(incident, {"status": "success", "read_only": True, "real_llm_executed": False, "scenarios": [{"status": "success"}]})
    _write_json(
        handoff,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": False,
            "handoff_items": [{"status": "ready"}],
            "known_limitations": ["公网直上 No-Go"],
        },
    )
    _write_json(
        readiness,
        {
            "readiness_status": "ready",
            "read_only": True,
            "real_llm_executed": False,
            "integrations": [{"readiness_status": "ready"}],
        },
    )
    _write_json(
        comparison,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": False,
            "comparison": {"added_count": 1, "removed_count": 0, "changed_count": 0},
        },
    )

    summary = build_operator_drill_scoring(
        output_dir=tmp_path / "out",
        incident_report=incident,
        handoff_report=handoff,
        integration_readiness=readiness,
        evidence_comparison=comparison,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["version"] == "3.5.0"
    assert payload["overall_score"] == 100
    assert payload["risk_level"] == "low"
    assert [item["dimension"] for item in payload["dimension_scores"]] == [
        "availability",
        "recoverability",
        "evidence_integrity",
        "configuration_readiness",
        "permission_boundary",
        "known_limitations",
    ]
    assert payload["read_only"] is True
    assert payload["real_llm_executed"] is False
    assert Path(summary["markdown_path"]).exists()


def test_operator_drill_scoring_missing_inputs_skipped(tmp_path: Path) -> None:
    summary = build_operator_drill_scoring(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert payload["status"] == "skipped"
    assert payload["overall_score"] == 0
    assert payload["risk_level"] == "high"
    assert "incident_report:input_not_provided" in payload["missing_conditions"]
    assert "handoff_report:input_not_provided" in payload["missing_conditions"]
    assert "integration_readiness:input_not_provided" in payload["missing_conditions"]
    assert "evidence_comparison:input_not_provided" in payload["missing_conditions"]


def test_operator_drill_scoring_preserves_source_skipped_semantics(tmp_path: Path) -> None:
    incident = tmp_path / "incident.json"
    handoff = tmp_path / "handoff.json"
    readiness = tmp_path / "readiness.json"
    comparison = tmp_path / "comparison.json"
    _write_json(incident, {"status": "skipped", "missing_conditions": ["service_unavailable"], "real_llm_executed": False})
    _write_json(handoff, {"status": "success", "known_limitations": ["真实 LLM 仅 opt-in"], "real_llm_executed": False})
    _write_json(readiness, {"readiness_status": "skipped", "skipped_reasons": ["REAL_LLM_API_KEY_ENV_TARGET"], "real_llm_executed": False})
    _write_json(comparison, {"status": "success", "comparison": {"added_count": 0, "removed_count": 0, "changed_count": 0}})

    summary = build_operator_drill_scoring(
        output_dir=tmp_path / "out",
        incident_report=incident,
        handoff_report=handoff,
        integration_readiness=readiness,
        evidence_comparison=comparison,
    )
    payload = _read_payload(summary)
    source_status = {item["name"]: item["status"] for item in payload["input_sources"]}
    dimension_status = {item["dimension"]: item["status"] for item in payload["dimension_scores"]}

    assert summary["status"] == "partial"
    assert source_status["incident_report"] == "skipped"
    assert source_status["integration_readiness"] == "skipped"
    assert dimension_status["availability"] == "skipped"
    assert dimension_status["configuration_readiness"] == "skipped"
    assert "incident_report:source_status_skipped" in payload["missing_conditions"]
    assert "integration_readiness:source_status_skipped" in payload["missing_conditions"]
    assert "REAL_LLM_API_KEY_ENV_TARGET" in payload["missing_conditions"]


def test_operator_drill_scoring_does_not_leak_unknown_secret_fields(tmp_path: Path) -> None:
    incident = tmp_path / "incident.json"
    _write_json(
        incident,
        {
            "status": "success",
            "read_only": True,
            "real_llm_executed": False,
            "api_key": "sk-should-not-leak",
            "DATABASE_URL": "postgresql://demo:secret@localhost/db",
            "scenarios": [{"status": "success", "client_secret": "should-not-leak"}],
        },
    )

    summary = build_operator_drill_scoring(output_dir=tmp_path / "out", incident_report=incident)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + "\n" + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "sk-should-not-leak" not in merged
    assert "postgresql://demo:secret@" not in merged
    assert "should-not-leak" not in merged
    assert "incident_report" in merged
