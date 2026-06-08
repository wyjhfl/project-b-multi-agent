from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_landing_status"

REPORT_SOURCES = {
    "env_check": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_env_check",
        "pattern": "*_production_landing_env_check.json",
    },
    "execution_gate": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_execution_gate",
        "pattern": "*_production_landing_execution_gate.json",
    },
    "real_llm_preflight": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_real_llm_preflight",
        "pattern": "*_production_landing_real_llm_preflight.json",
    },
    "xiaomi_llm_preflight": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_xiaomi_llm_preflight",
        "pattern": "*_production_landing_xiaomi_llm_preflight.json",
    },
    "business_read_smoke": {
        "dir": ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
        "pattern": "*_business_system_read_smoke.json",
    },
    "business_real_readiness_gate": {
        "dir": ROOT_DIR / "docs" / "reports" / "business_system_real_readiness_gate",
        "pattern": "*_business_system_real_readiness_gate.json",
    },
    "business_production_readiness": {
        "dir": ROOT_DIR / "docs" / "reports" / "business_system_production_readiness",
        "pattern": "*_business_system_production_readiness.json",
    },
    "business_landing_execution_pack": {
        "dir": ROOT_DIR / "docs" / "reports" / "business_system_landing_execution_pack",
        "pattern": "*_business_system_landing_execution_pack.json",
    },
    "action_pack": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_landing_action_pack",
        "pattern": "*_production_landing_action_pack.json",
    },
    "pilot_signoff": {
        "dir": ROOT_DIR / "docs" / "reports" / "production_pilot_signoff",
        "pattern": "*_production_pilot_signoff.json",
    },
    "manual_signoff_record_validation": {
        "dir": ROOT_DIR / "docs" / "reports" / "manual_signoff_record_validation",
        "pattern": "*_manual_signoff_record_validation.json",
    },
}

MANUAL_SIGNOFF_RECORD_PATH = ROOT_DIR / "docs" / "reports" / "manual_signoff_package" / "manual_signoff_record.json"
REQUIRED_MANUAL_SIGNOFF_ROLES = ("release_manager", "security_reviewer", "business_owner", "operations_owner")

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bk-[A-Za-z0-9_\-]{24,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]
SAFE_SECRET_PLACEHOLDERS = {
    "<secret-managed-token>",
    "<secret-managed-url>",
    "<external-secret-managed-url>",
    "<secret-managed-value>",
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "secret-managed-value",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_like(key) or _contains_secret_like(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like(item) for item in value)
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if len(match.groups()) >= 2 and str(match.group(2)).strip().strip(".,;") in SAFE_SECRET_PLACEHOLDERS:
            continue
        return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items()}
    return value


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(item: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
        return (generated_at, item.stat().st_mtime, item.name)

    return max(files, key=sort_key)


def _read_latest(source_id: str) -> dict[str, Any]:
    spec = REPORT_SOURCES[source_id]
    latest = _latest_json(Path(spec["dir"]), str(spec["pattern"]))
    if latest is None:
        return {
            "source_id": source_id,
            "present": False,
            "status": "skipped",
            "latest_json_path": "",
            "payload": {},
            "missing_conditions": [f"{source_id}:report_not_found"],
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "source_id": source_id,
            "present": True,
            "status": "blocked",
            "latest_json_path": str(latest),
            "payload": {},
            "missing_conditions": [f"{source_id}:json_parse_failed"],
        }
    if not isinstance(payload, dict):
        payload = {}
    return {
        "source_id": source_id,
        "present": True,
        "status": str(payload.get("status") or "skipped"),
        "latest_json_path": str(latest),
        "payload": payload,
        "missing_conditions": [str(item) for item in payload.get("missing_conditions", [])]
        if isinstance(payload.get("missing_conditions"), list)
        else [],
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _formal_manual_signoff_record_summary() -> dict[str, Any]:
    record = _read_json_file(MANUAL_SIGNOFF_RECORD_PATH)
    if not record:
        return {"completed": False, "record_present": False, "decision": ""}
    roles = record.get("roles") if isinstance(record.get("roles"), list) else []
    role_by_id = {str(item.get("role") or ""): item for item in roles if isinstance(item, dict)}
    roles_ready = all(
        (
            (item := role_by_id.get(role)) is not None
            and str(item.get("name") or "").strip()
            and item.get("approved") is True
        )
        for role in REQUIRED_MANUAL_SIGNOFF_ROLES
    )
    completed = (
        record.get("manual_signoff_completed") is True
        and str(record.get("decision") or "").strip().lower() == "go"
        and str(record.get("public_production_direct_launch") or "").strip().lower() == "no-go"
        and record.get("auto_signed") is not True
        and record.get("auto_approved") is not True
        and record.get("auto_closed") is not True
        and roles_ready
    )
    return {
        "completed": completed,
        "record_present": True,
        "decision": str(record.get("decision") or ""),
    }


def _manual_signoff_summary(*, pilot_payload: dict[str, Any], validation_payload: dict[str, Any]) -> dict[str, Any]:
    validation_completed = (
        validation_payload.get("status") == "success"
        and validation_payload.get("manual_signoff_completed") is True
        and int(validation_payload.get("missing_condition_count") or 0) == 0
    )
    if validation_completed:
        return {
            "completed": True,
            "record_present": bool(validation_payload.get("signoff_record_present", True)),
            "decision": str(validation_payload.get("decision") or "Go"),
        }
    formal = _formal_manual_signoff_record_summary()
    if formal["completed"]:
        return formal
    return {
        "completed": bool(pilot_payload.get("manual_signoff_completed", False)),
        "record_present": bool(pilot_payload.get("manual_signoff_record_present", False)),
        "decision": str(pilot_payload.get("manual_signoff_decision") or ""),
    }


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    payload = source.get("payload") if isinstance(source.get("payload"), dict) else {}
    return {
        "source_id": source["source_id"],
        "present": bool(source.get("present", False)),
        "status": str(source.get("status") or "skipped"),
        "latest_json_path": str(source.get("latest_json_path") or ""),
        "generated_at": str(payload.get("generated_at") or ""),
    }


def _dedupe_commands(commands: list[str]) -> list[str]:
    result: list[str] = []
    for command in commands:
        text = _normalize_windows_safe_command(str(command).strip())
        if text and text not in result:
            result.append(text)
    return result


def _normalize_windows_safe_command(command: str) -> str:
    if command.startswith("python scripts/"):
        return "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 " + command.removeprefix(
            "python "
        ).replace("/", "\\")
    if command.startswith("python -m "):
        return "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 " + command.removeprefix(
            "python "
        )
    return command


def _business_system_priority_commands(
    *,
    business_real_gate: dict[str, Any],
    business_execution_pack: dict[str, Any],
) -> list[str]:
    pack_command = str(
        business_execution_pack.get("recommended_next_command")
        or business_execution_pack.get("safe_next_action")
        or ""
    ).strip()
    pack_ready = business_execution_pack.get("ready_for_real_read_smoke") is True
    smoke_complete = business_execution_pack.get("real_read_smoke_complete") is True
    real_gate_ready = business_real_gate.get("ready_for_real_read_smoke") is True

    if smoke_complete:
        return [
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_landing_resume.ps1 -UseExistingEnv -EnvPath local\\production_landing.staging.env"
        ]
    if real_gate_ready and pack_ready:
        if not pack_command.lower().startswith("powershell "):
            pack_command = ""
        return _dedupe_commands(
            [
                pack_command,
                "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -UseExistingEnv",
            ]
        )
    return [
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1 -PreflightOnly -EnvPath local\\production_landing.staging.env",
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 scripts\\business_system_real_readiness_gate.py --env-path local\\production_landing.staging.env",
    ]


def _derive_next_commands(
    gate: dict[str, Any],
    action_pack: dict[str, Any],
    *,
    blockers: list[str] | None = None,
    business_real_gate: dict[str, Any] | None = None,
    business_execution_pack: dict[str, Any] | None = None,
) -> list[str]:
    commands = gate.get("safe_runner_commands") if isinstance(gate.get("safe_runner_commands"), list) else []
    recommended = action_pack.get("recommended_commands") if isinstance(action_pack.get("recommended_commands"), list) else []
    base_commands = [str(item) for item in [*commands, *recommended]]
    priority_commands: list[str] = []
    if "business_system:real_read_smoke_required" in (blockers or []):
        priority_commands = _business_system_priority_commands(
            business_real_gate=business_real_gate or {},
            business_execution_pack=business_execution_pack or {},
        )
    return _dedupe_commands([*priority_commands, *base_commands])[:12]


def _blocking_required_inputs(action_pack: dict[str, Any]) -> list[str]:
    inputs = action_pack.get("required_inputs") if isinstance(action_pack.get("required_inputs"), list) else []
    blocking: list[str] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        input_id = str(item.get("input_id") or "")
        if input_id in {"real_infra_current_round_acceptance", "business_system_read_only_credentials"}:
            continue
        blocking.append(input_id or "unknown")
    return blocking


def _select_real_llm_preflight_source(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    real_source = sources.get("real_llm_preflight", {})
    if real_source.get("present"):
        return real_source
    return sources.get("xiaomi_llm_preflight", {})


def _real_llm_preflight_success(payload: dict[str, Any]) -> bool:
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    blockers = payload.get("acceptance_blockers") if isinstance(payload.get("acceptance_blockers"), list) else []
    return bool(
        payload.get("status") == "success"
        and payload.get("api_key_present") is True
        and payload.get("real_llm_executed") is True
        and preflight.get("network_check_executed") is True
        and payload.get("secret_plaintext_output") is False
        and not blockers
    )


def _only_real_llm_env_blocked_by_local_placeholder(payload: dict[str, Any]) -> bool:
    domains = payload.get("domains") if isinstance(payload.get("domains"), list) else []
    blocked = [item for item in domains if isinstance(item, dict) and item.get("ready_for_execute") is not True]
    if len(blocked) != 1:
        return False
    item = blocked[0]
    placeholder_keys = [str(key) for key in (item.get("placeholder_keys") if isinstance(item.get("placeholder_keys"), list) else [])]
    real_llm_secret_placeholders = {
        key
        for key in placeholder_keys
        if key in {"REAL_LLM_API_KEY", "XIAOMI_LLM_API_KEY"} or key.endswith("_LLM_API_KEY") or key.endswith("_API_KEY")
    }
    return bool(
        item.get("domain_id") == "real_llm"
        and str(item.get("blocker_reason") or "") == "placeholder_env"
        and real_llm_secret_placeholders
    )


def _real_llm_status_summary(payload: dict[str, Any], source_id: str) -> dict[str, Any]:
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    return {
        "source_id": source_id,
        "status": str(payload.get("status") or "skipped"),
        "provider": str(payload.get("provider") or preflight.get("provider") or ""),
        "model": str(payload.get("real_llm_model") or preflight.get("model") or ""),
        "api_key_env": str(payload.get("api_key_env") or preflight.get("api_key_env") or ""),
        "api_key_present": bool(payload.get("api_key_present", False)),
        "network_check_requested": bool(preflight.get("network_check_requested", payload.get("execute_network_check", False))),
        "network_check_allowed": bool(preflight.get("network_check_allowed", False)),
        "network_check_executed": bool(preflight.get("network_check_executed", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "safe_next_action": str(payload.get("safe_next_action") or ""),
        "acceptance_blockers": [
            str(item)
            for item in (payload.get("acceptance_blockers") if isinstance(payload.get("acceptance_blockers"), list) else [])
        ],
        "safe_preflight_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_llm_preflight.ps1",
        "compat_xiaomi_preflight_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1",
    }


def _derive_status(
    *,
    env_check: dict[str, Any],
    gate: dict[str, Any],
    real_llm_preflight: dict[str, Any],
    business: dict[str, Any],
    business_real_gate: dict[str, Any],
    business_readiness: dict[str, Any],
    business_execution_pack: dict[str, Any],
    action_pack: dict[str, Any],
    pilot_signoff: dict[str, Any],
    manual_signoff_validation: dict[str, Any],
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if any(
        source.get("status") in {"blocked", "failed"}
        for source in [
            env_check,
            gate,
            real_llm_preflight,
            business,
            business_real_gate,
            business_readiness,
            business_execution_pack,
            action_pack,
            pilot_signoff,
            manual_signoff_validation,
        ]
    ):
        blockers.append("source_status:blocked_or_failed")

    gate_payload = gate.get("payload") if isinstance(gate.get("payload"), dict) else {}
    env_payload = env_check.get("payload") if isinstance(env_check.get("payload"), dict) else {}
    business_payload = business.get("payload") if isinstance(business.get("payload"), dict) else {}
    business_real_gate_payload = (
        business_real_gate.get("payload")
        if isinstance(business_real_gate.get("payload"), dict)
        else {}
    )
    business_execution_payload = (
        business_execution_pack.get("payload")
        if isinstance(business_execution_pack.get("payload"), dict)
        else {}
    )
    action_payload = action_pack.get("payload") if isinstance(action_pack.get("payload"), dict) else {}
    pilot_payload = pilot_signoff.get("payload") if isinstance(pilot_signoff.get("payload"), dict) else {}
    validation_payload = (
        manual_signoff_validation.get("payload")
        if isinstance(manual_signoff_validation.get("payload"), dict)
        else {}
    )
    real_llm_payload = (
        real_llm_preflight.get("payload")
        if isinstance(real_llm_preflight.get("payload"), dict)
        else {}
    )
    local_llm_env_gap_covered_by_real_preflight = bool(
        _real_llm_preflight_success(real_llm_payload)
        and (
            _only_real_llm_env_blocked_by_local_placeholder(env_payload)
            or int(env_payload.get("ready_domain_count", 0) or 0) >= int(env_payload.get("domain_count", 5) or 5)
        )
        and _only_real_llm_env_blocked_by_local_placeholder(gate_payload)
    )

    if (
        bool(gate_payload.get("execution_allowed", False)) is not True
        and not local_llm_env_gap_covered_by_real_preflight
    ):
        blockers.append("execution_gate:not_allowed")
    if (
        int(env_payload.get("ready_domain_count", 0) or 0) < int(env_payload.get("domain_count", 5) or 5)
        and not local_llm_env_gap_covered_by_real_preflight
    ):
        blockers.append("env_check:not_all_domains_ready")
    if _blocking_required_inputs(action_payload):
        blockers.append("action_pack:required_inputs_remaining")
    if (
        business_execution_payload.get("status") != "ready"
        or business_execution_payload.get("real_read_smoke_complete") is not True
    ):
        missing_conditions = (
            business_execution_payload.get("missing_conditions")
            if isinstance(business_execution_payload.get("missing_conditions"), list)
            else []
        )
        if "evidence:local_business_mock_not_valid_for_real_production" in missing_conditions:
            blockers.append("business_system:real_read_smoke_required")
        elif "evidence:demo_business_system_not_valid_for_real_production" in missing_conditions:
            blockers.append("business_system:real_business_system_required")
        elif "evidence:business_system_real_read_smoke_not_executed" in missing_conditions:
            blockers.append("business_system:real_read_smoke_required")
        else:
            blockers.append("business_landing_execution_pack:not_ready")
    if business_real_gate_payload.get("ready_for_real_read_smoke") is not True:
        missing_conditions = (
            business_real_gate_payload.get("missing_conditions")
            if isinstance(business_real_gate_payload.get("missing_conditions"), list)
            else []
        )
        if "business_system:local_mock_configured" in missing_conditions:
            blockers.append("business_system:real_config_required")
        if "business_system:demo_business_system_configured" in missing_conditions:
            blockers.append("business_system:real_business_system_required")

    manual_signoff = _manual_signoff_summary(
        pilot_payload=pilot_payload,
        validation_payload=validation_payload,
    )
    if manual_signoff.get("completed") is not True:
        blockers.append("manual_signoff:not_completed")

    if "source_status:blocked_or_failed" in blockers:
        return "blocked", sorted(set(blockers))
    return ("success" if not blockers else "partial"), sorted(set(blockers))


def build_production_landing_status(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    sources = {source_id: _read_latest(source_id) for source_id in REPORT_SOURCES}
    real_llm_source = _select_real_llm_preflight_source(sources)
    payloads = {source_id: source.get("payload", {}) for source_id, source in sources.items()}
    status, blockers = _derive_status(
        env_check=sources["env_check"],
        gate=sources["execution_gate"],
        real_llm_preflight=real_llm_source,
        business=sources["business_read_smoke"],
        business_real_gate=sources["business_real_readiness_gate"],
        business_readiness=sources["business_production_readiness"],
        business_execution_pack=sources["business_landing_execution_pack"],
        action_pack=sources["action_pack"],
        pilot_signoff=sources["pilot_signoff"],
        manual_signoff_validation=sources["manual_signoff_record_validation"],
    )
    gate = payloads.get("execution_gate", {})
    env_check = payloads.get("env_check", {})
    real_llm = real_llm_source.get("payload") if isinstance(real_llm_source.get("payload"), dict) else {}
    real_llm_summary = _real_llm_status_summary(real_llm, str(real_llm_source.get("source_id") or "real_llm_preflight"))
    business = payloads.get("business_read_smoke", {})
    business_real_gate = payloads.get("business_real_readiness_gate", {})
    business_readiness = payloads.get("business_production_readiness", {})
    business_execution_pack = payloads.get("business_landing_execution_pack", {})
    action_pack = payloads.get("action_pack", {})
    pilot = payloads.get("pilot_signoff", {})
    validation = payloads.get("manual_signoff_record_validation", {})
    manual_signoff = _manual_signoff_summary(pilot_payload=pilot, validation_payload=validation)
    landing = pilot.get("landing_status") if isinstance(pilot.get("landing_status"), dict) else {}
    raw_next_commands = _derive_next_commands(
        gate,
        action_pack,
        blockers=blockers,
        business_real_gate=business_real_gate,
        business_execution_pack=business_execution_pack,
    )
    secret_like_detected = _contains_secret_like(raw_next_commands)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    summary = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.7.2",
        "phase": "v4.7 Production Landing Status",
        "status": status,
        "mode": "read_only_landing_status",
        "sources": {source_id: _source_summary(source) for source_id, source in sources.items()},
        "ready_domains": _redact(gate.get("ready_domains", [])),
        "blocked_domains": _redact(gate.get("blocked_domains", [])),
        "ready_domain_count": int(gate.get("ready_domain_count", env_check.get("ready_domain_count", 0)) or 0),
        "domain_count": int(gate.get("requested_domain_count", env_check.get("domain_count", 0)) or 0),
        "execution_allowed": bool(gate.get("execution_allowed", False)),
        "real_llm": real_llm_summary,
        "xiaomi_llm": real_llm_summary,
        "business_system": {
            "status": str(business.get("status") or "skipped"),
            "real_readiness_gate_status": str(business_real_gate.get("status") or "skipped"),
            "real_readiness_gate_ready": bool(business_real_gate.get("ready_for_real_read_smoke", False)),
            "real_readiness_gate_local_mock_configured": bool(
                business_real_gate.get("local_mock_configured", False)
            ),
            "real_readiness_gate_demo_business_configured": bool(
                business_real_gate.get("demo_business_system_configured", False)
            ),
            "real_readiness_gate_missing_conditions": [
                str(item)
                for item in (
                    business_real_gate.get("missing_conditions")
                    if isinstance(business_real_gate.get("missing_conditions"), list)
                    else []
                )[:16]
            ],
            "connected": bool(business.get("business_system_connected", False)),
            "read_executed": bool(business.get("business_read_executed", False)),
            "write_executed": bool(business.get("business_write_executed", False)),
            "business_data_written": bool(business.get("business_data_written", False)),
            "local_mock_used": bool(business.get("local_business_mock_used", False)),
            "demo_system_used": bool(business.get("demo_business_system_used", False))
            or bool(
                (
                    business_execution_pack.get("business_system_read_smoke")
                    if isinstance(business_execution_pack.get("business_system_read_smoke"), dict)
                    else {}
                ).get("demo_business_system_used", False)
            ),
            "real_system_connected": bool(business.get("business_system_connected", False))
            and bool(business.get("local_business_mock_used", False)) is not True
            and bool(business.get("demo_business_system_used", False)) is not True,
            "real_read_smoke_required_for_public_production": True,
            "real_read_smoke_gap": bool(business.get("business_read_executed", False)) is not True
            or bool(business.get("local_business_mock_used", False)) is True
            or bool(business.get("demo_business_system_used", False)) is True,
            "production_readiness_status": str(business_readiness.get("status") or "skipped"),
            "production_readiness_missing_count": int(business_readiness.get("missing_condition_count") or 0),
            "production_readiness_missing_conditions": [
                str(item)
                for item in (
                    business_readiness.get("missing_conditions")
                    if isinstance(business_readiness.get("missing_conditions"), list)
                    else []
                )[:16]
            ],
            "production_readiness_public_production_gap": str(business_readiness.get("status") or "skipped")
            != "ready",
            "landing_execution_pack_status": str(business_execution_pack.get("status") or "skipped"),
            "landing_execution_ready_for_real_read_smoke": bool(
                business_execution_pack.get("ready_for_real_read_smoke", False)
            ),
            "landing_execution_real_read_smoke_complete": bool(
                business_execution_pack.get("real_read_smoke_complete", False)
            ),
            "landing_execution_safe_next_action": str(business_execution_pack.get("safe_next_action") or ""),
            "landing_execution_missing_count": int(
                business_execution_pack.get("missing_condition_count") or 0
            ),
            "landing_execution_missing_conditions": [
                str(item)
                for item in (
                    business_execution_pack.get("missing_conditions")
                    if isinstance(business_execution_pack.get("missing_conditions"), list)
                    else []
                )[:16]
            ],
            "real_read_smoke_next_command": str(
                business_execution_pack.get("recommended_next_command")
                or business_execution_pack.get("safe_next_action")
                or ""
            ),
        },
        "manual_signoff": {
            "completed": bool(manual_signoff.get("completed", False)),
            "record_present": bool(manual_signoff.get("record_present", False)),
            "decision": str(manual_signoff.get("decision") or ""),
        },
        "landing_state": str(landing.get("enterprise_landing_state") or "needs-local-evidence"),
        "required_input_count": len(_blocking_required_inputs(action_pack)),
        "non_blocking_required_input_count": max(
            int(action_pack.get("required_input_count", 0) or 0) - len(_blocking_required_inputs(action_pack)),
            0,
        ),
        "next_commands": _redact(raw_next_commands),
        "blockers": blockers,
        "controlled_pilot_ready": status == "success",
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }
    if secret_like_detected or _contains_secret_like(summary):
        summary["status"] = "blocked"
        summary["secret_plaintext_output"] = True
        summary["blockers"] = sorted(set([*blockers, "landing_status:secret_like_output_detected"]))

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_landing_status"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(summary), encoding="utf-8")
    return {
        "status": summary["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "controlled_pilot_ready": summary["controlled_pilot_ready"],
        "blocker_count": len(summary["blockers"]),
        "secret_plaintext_output": summary["secret_plaintext_output"],
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Production Landing Status",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- controlled_pilot_ready: {payload.get('controlled_pilot_ready', False)}",
        f"- ready_domain_count: {payload.get('ready_domain_count', 0)}/{payload.get('domain_count', 0)}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        "",
        "## Blockers",
    ]
    blockers = payload.get("blockers", [])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Next Commands"])
    commands = payload.get("next_commands", [])
    if commands:
        lines.extend(f"- `{item}`" for item in commands)
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only summarized production landing status.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--strict", action="store_true", help="Return non-zero when status is not success.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_status(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    if not args.strict:
        return 0
    if summary["status"] == "success":
        return 0
    if summary["status"] == "partial":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
