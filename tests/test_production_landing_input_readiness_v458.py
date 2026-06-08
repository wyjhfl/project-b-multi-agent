from __future__ import annotations

import json
import os
from pathlib import Path

import scripts.production_landing_input_readiness as readiness
from scripts.production_landing_input_readiness import build_production_landing_input_readiness


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _write_business_env(path: Path, *, token: str = "local-token-value") -> None:
    path.write_text(
        "\n".join(
            [
                "BUSINESS_INTEGRATION_ENABLED=true",
                "BUSINESS_INTEGRATION_READ_ONLY=true",
                "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
                "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
                "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
                "BUSINESS_SYSTEM_NAME=crm",
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
        )
        + "\n",
        encoding="utf-8",
    )


def _closure_payload() -> dict:
    return {
        "status": "partial",
        "read_only": True,
        "auto_approved": False,
        "auto_closed": False,
        "closure_items": [
            {
                "blocker_id": "LB-001",
                "source_key": "business_system_integration_acceptance_missing",
                "owner": "ops-owner",
                "due_at": "2026-06-10",
                "compensating_controls": ["read-only smoke evidence reviewed"],
                "closure_evidence_refs": ["docs/reports/business_system_read_smoke/safe.json"],
                "reviewer": "security-reviewer",
                "approval_state": "pending_review",
            }
        ],
    }


def _signoff_payload() -> dict:
    return {
        "manual_signoff_completed": True,
        "decision": "Go",
        "signed_at": "2026-06-04T00:00:00+00:00",
        "public_production_direct_launch": "No-Go",
        "auto_signed": False,
        "auto_approved": False,
        "roles": [
            {"role": "release_manager", "name": "release", "approved": True},
            {"role": "security_reviewer", "name": "security", "approved": True},
            {"role": "business_owner", "name": "business", "approved": True},
            {"role": "operations_owner", "name": "ops", "approved": True},
        ],
        "evidence_acknowledgements": [
            {"item": "real_llm_preflight", "accepted": True},
            {"item": "postgres_redis_mcp_smoke", "accepted": True},
            {"item": "business_read_smoke", "accepted": True},
            {"item": "closure_evidence_review", "accepted": True},
        ],
    }


def _pilot_signoff_payload(*, ready: bool = True) -> dict:
    return {
        "status": "partial",
        "landing_status": {
            "database_connected": ready,
            "redis_connected": ready,
            "external_mcp_connected": ready,
            "real_infra_ready": ready,
            "production_blockers": [] if ready else ["real_infra:postgres_redis_mcp_not_all_connected"],
        },
        "secret_plaintext_output": False,
    }


def _business_smoke_payload() -> dict:
    return {
        "status": "success",
        "read_only": True,
        "business_system_connected": True,
        "business_read_executed": True,
        "business_write_executed": False,
        "business_data_written": False,
        "approval_bypassed": False,
        "audit_bypassed": False,
        "secret_plaintext_output": False,
    }


def test_production_landing_input_readiness_default_templates_are_partial(tmp_path: Path) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    signoff = tmp_path / "signoff.json"
    pilot = tmp_path / "pilot_signoff.json"
    business_env.write_text(
        "BUSINESS_INTEGRATION_ENABLED=true\n"
        "BUSINESS_INTEGRATION_READ_ONLY=true\n"
        "BUSINESS_INTEGRATION_WRITE_ENABLED=false\n"
        "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true\n"
        "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true\n"
        "BUSINESS_SYSTEM_NAME=<system-name>\n"
        "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL\n"
        "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN\n"
        "BUSINESS_SYSTEM_BASE_URL=<https://business-system.example.com>\n"
        "BUSINESS_SYSTEM_TOKEN=<set-in-local-env-only>\n"
        "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe\n",
        encoding="utf-8",
    )
    _write_json(
        closure,
        {
            "read_only": True,
            "auto_approved": False,
            "auto_closed": False,
            "closure_items": [
                {
                    "blocker_id": "LB-001",
                    "owner": "manual_owner_required",
                    "due_at": "manual_due_date_required",
                    "compensating_controls": ["manual_compensating_controls_required"],
                    "closure_evidence_refs": ["manual_closure_evidence_required"],
                    "reviewer": "",
                    "approval_state": "not_approved",
                }
            ],
        },
    )
    _write_json(
        signoff,
        {
            "manual_signoff_completed": False,
            "decision": "No-Go",
            "public_production_direct_launch": "No-Go",
            "auto_signed": False,
            "auto_approved": False,
            "roles": [],
        },
    )
    _write_json(pilot, _pilot_signoff_payload(ready=False))

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        closure_evidence=closure,
        manual_signoff=signoff,
        pilot_signoff=pilot,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "partial"
    assert summary["ready_input_count"] == 0
    assert summary["missing_input_count"] == 4
    assert summary["blocked_input_count"] == 0
    assert payload["missing_input_count"] == 4
    assert payload["blocked_input_count"] == 0
    assert payload["source_reports"]["pilot_signoff"] == str(pilot)
    assert payload["resolved_paths"]["manual_signoff"] == str(signoff)
    assert payload["public_production_direct_launch"] == "No-Go"
    assert payload["secret_plaintext_output"] is False
    assert payload["inputs"][0]["status"] == "partial"
    assert payload["inputs"][0]["next_action"]
    assert payload["inputs"][0]["command_after_fill"] == "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in payload["inputs"][0]["required_env"]
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization" in payload["inputs"][0]["required_env"]
    assert "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer" in payload["inputs"][0]["required_env"]
    assert "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>" in payload["inputs"][0]["required_env"]
    assert "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>" in payload["inputs"][0]["required_env"]
    assert "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>" in payload["inputs"][0]["required_env"]
    assert "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>" in payload["inputs"][0]["required_env"]
    assert "business_env:BUSINESS_SYSTEM_AUTH_HEADER_NAME_not_filled" in payload["inputs"][0]["missing_conditions"]
    assert "business_env:BUSINESS_SYSTEM_BUSINESS_OWNER_not_filled" in payload["inputs"][0]["missing_conditions"]
    assert payload["inputs"][1]["status"] == "partial"
    assert payload["inputs"][2]["status"] == "partial"
    assert "scripts\\real_llm_preflight.ps1" in payload["inputs"][2]["command_after_fill"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains postgres" in payload["inputs"][2]["command_after_fill"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains redis" in payload["inputs"][2]["command_after_fill"]
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp" in payload["inputs"][2]["command_after_fill"]
    assert "REAL_LLM_MODEL=gpt-5.5" in payload["inputs"][2]["required_env"]
    assert "REAL_LLM_BASE_URL=http://100.119.206.22:8300/v1" in payload["inputs"][2]["required_env"]
    assert "REAL_LLM_API_KEY=<secret-managed-token>" in payload["inputs"][2]["required_env"]
    assert "DATABASE_URL=<secret-managed-url>" in payload["inputs"][2]["required_env"]
    assert payload["inputs"][3]["status"] == "partial"


def test_production_landing_input_readiness_success_when_all_inputs_ready(tmp_path: Path) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    signoff = tmp_path / "signoff.json"
    pilot = tmp_path / "pilot_signoff.json"
    _write_business_env(business_env)
    _write_json(closure, _closure_payload())
    _write_json(signoff, _signoff_payload())
    _write_json(pilot, _pilot_signoff_payload(ready=True))

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        closure_evidence=closure,
        manual_signoff=signoff,
        pilot_signoff=pilot,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert summary["ready_input_count"] == 4
    assert summary["missing_input_count"] == 0
    assert payload["missing_input_count"] == 0
    assert {item["status"] for item in payload["inputs"]} == {"ready"}
    assert all("command_after_fill" not in item for item in payload["inputs"])
    assert payload["auto_approved"] is False
    assert payload["auto_closed"] is False
    assert payload["business_system_connected"] is False


def test_production_landing_input_readiness_prefers_filled_manual_signoff(
    tmp_path: Path, monkeypatch
) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    pilot = tmp_path / "pilot_signoff.json"
    signoff_dir = tmp_path / "manual_signoff_package"
    template = signoff_dir / "manual_signoff_record.template.json"
    filled = signoff_dir / "manual_signoff_record.json"
    _write_business_env(business_env)
    _write_json(closure, _closure_payload())
    _write_json(pilot, _pilot_signoff_payload(ready=True))
    _write_json(template, {"manual_signoff_completed": False, "decision": "No-Go", "roles": []})
    _write_json(filled, _signoff_payload())
    monkeypatch.setattr(readiness, "DEFAULT_MANUAL_SIGNOFF", template)
    monkeypatch.setattr(readiness, "DEFAULT_FILLED_MANUAL_SIGNOFF", filled)
    monkeypatch.setattr(readiness, "DEFAULT_DRAFT_MANUAL_SIGNOFF", signoff_dir / "manual_signoff_record.draft.json")

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        closure_evidence=closure,
        pilot_signoff=pilot,
    )
    payload = _read_payload(summary)

    assert summary["status"] == "success"
    assert payload["resolved_paths"]["manual_signoff"] == str(filled)


def test_production_landing_input_readiness_accepts_successful_business_read_smoke(
    tmp_path: Path,
) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    signoff = tmp_path / "signoff.json"
    pilot = tmp_path / "pilot_signoff.json"
    smoke = tmp_path / "business_smoke.json"
    business_env.write_text("", encoding="utf-8")
    _write_json(closure, _closure_payload())
    _write_json(signoff, _signoff_payload())
    _write_json(pilot, _pilot_signoff_payload(ready=True))
    _write_json(smoke, _business_smoke_payload())

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        business_smoke=smoke,
        closure_evidence=closure,
        manual_signoff=signoff,
        pilot_signoff=pilot,
    )
    payload = _read_payload(summary)
    business = next(item for item in payload["inputs"] if item["input_id"] == "business_system_read_only_credentials")

    assert summary["status"] == "success"
    assert business["status"] == "ready"
    assert business["evidence_source"] == "business_system_read_smoke"
    assert business["business_read_executed"] is True
    assert business["business_data_written"] is False


def test_production_landing_input_readiness_rejects_local_business_mock_smoke(
    tmp_path: Path,
) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    signoff = tmp_path / "signoff.json"
    pilot = tmp_path / "pilot_signoff.json"
    smoke = tmp_path / "business_smoke.json"
    business_env.write_text("", encoding="utf-8")
    _write_json(closure, _closure_payload())
    _write_json(signoff, _signoff_payload())
    _write_json(pilot, _pilot_signoff_payload(ready=True))
    local_smoke = _business_smoke_payload()
    local_smoke["local_business_mock_used"] = True
    _write_json(smoke, local_smoke)

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        business_smoke=smoke,
        closure_evidence=closure,
        manual_signoff=signoff,
        pilot_signoff=pilot,
    )
    payload = _read_payload(summary)
    business = next(item for item in payload["inputs"] if item["input_id"] == "business_system_read_only_credentials")

    assert summary["status"] == "partial"
    assert business["status"] == "partial"
    assert business["local_business_mock_used"] is True
    assert "business_smoke:local_business_mock_not_valid_for_real_production" in business["missing_conditions"]


def test_production_landing_input_readiness_blocks_secret_like_json_without_leak(tmp_path: Path) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    signoff = tmp_path / "signoff.json"
    pilot = tmp_path / "pilot_signoff.json"
    key_value = "sk-" + "landing-secret"
    _write_business_env(business_env)
    closure_payload = _closure_payload()
    closure_payload["api_key"] = key_value
    _write_json(closure, closure_payload)
    _write_json(signoff, _signoff_payload())
    _write_json(pilot, _pilot_signoff_payload(ready=True))

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        closure_evidence=closure,
        manual_signoff=signoff,
        pilot_signoff=pilot,
    )
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert summary["status"] == "blocked"
    assert payload["blocked_input_count"] == 1
    assert "closure_evidence:secret_like_value_detected" in payload["inputs"][1]["missing_conditions"]
    assert key_value not in merged


def test_production_landing_input_readiness_tracks_real_infra_current_round(tmp_path: Path) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    signoff = tmp_path / "signoff.json"
    pilot = tmp_path / "pilot_signoff.json"
    _write_business_env(business_env)
    _write_json(closure, _closure_payload())
    _write_json(signoff, _signoff_payload())
    _write_json(pilot, _pilot_signoff_payload(ready=False))

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        closure_evidence=closure,
        manual_signoff=signoff,
        pilot_signoff=pilot,
    )
    payload = _read_payload(summary)
    infra = next(item for item in payload["inputs"] if item["input_id"] == "real_infra_current_round_acceptance")

    assert summary["status"] == "partial"
    assert summary["required_input_count"] == 4
    assert infra["status"] == "partial"
    assert infra["real_infra_ready"] is False
    assert "real_infra:postgres_redis_mcp_not_all_connected" in infra["missing_conditions"]


def test_production_landing_input_readiness_prefers_latest_pilot_signoff_by_generated_at(
    tmp_path: Path,
    monkeypatch,
) -> None:
    business_env = tmp_path / "business.env"
    closure = tmp_path / "closure.json"
    signoff = tmp_path / "signoff.json"
    pilot_dir = tmp_path / "production_pilot_signoff"
    pilot_dir.mkdir()
    current = pilot_dir / "100_current_production_pilot_signoff.json"
    stale = pilot_dir / "999_stale_production_pilot_signoff.json"
    _write_business_env(business_env)
    _write_json(closure, _closure_payload())
    _write_json(signoff, _signoff_payload())
    _write_json(current, {"generated_at": "2026-06-05T10:00:00+00:00", **_pilot_signoff_payload(ready=True)})
    _write_json(stale, {"generated_at": "2026-06-05T09:00:00+00:00", **_pilot_signoff_payload(ready=False)})
    os.utime(current, (1, 1))
    os.utime(stale, (2, 2))
    monkeypatch.setattr(readiness, "DEFAULT_PILOT_SIGNOFF_DIR", pilot_dir)

    summary = build_production_landing_input_readiness(
        output_dir=tmp_path / "out",
        business_env=business_env,
        closure_evidence=closure,
        manual_signoff=signoff,
    )
    payload = _read_payload(summary)
    infra = next(item for item in payload["inputs"] if item["input_id"] == "real_infra_current_round_acceptance")

    assert payload["source_reports"]["pilot_signoff"] == str(current)
    assert infra["status"] == "ready"
    assert summary["status"] == "success"
