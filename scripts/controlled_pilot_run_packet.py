from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_run_packet"

SOURCE_DIRS = {
    "controlled_pilot_delivery_gate": ROOT_DIR / "docs" / "reports" / "controlled_pilot_delivery_gate",
    "controlled_pilot_launch_gate": ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_gate",
    "controlled_pilot_launch_package": ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_package",
    "controlled_pilot_status_summary": ROOT_DIR / "docs" / "reports" / "controlled_pilot_status_summary",
    "controlled_pilot_operator_packet": ROOT_DIR / "docs" / "reports" / "controlled_pilot_operator_packet",
    "controlled_pilot_console_verify": ROOT_DIR / "docs" / "reports" / "controlled_pilot_console_verify",
    "production_landing_refresh_status": ROOT_DIR / "docs" / "reports" / "production_landing_refresh_status",
    "production_landing_status": ROOT_DIR / "docs" / "reports" / "production_landing_status",
    "business_system_read_smoke": ROOT_DIR / "docs" / "reports" / "business_system_read_smoke",
}

READY_SCOPE = "controlled_internal_pilot"
ACCEPTED_REMAINING_GAPS = {"business_system:real_business_system_required"}
REQUIRED_SOURCES = tuple(SOURCE_DIRS)

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"\btp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bk-[A-Za-z0-9_\-]{24,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]

SAFE_SECRET_PLACEHOLDERS = {
    "secret-managed-token",
    "secret-managed-url",
    "external-secret-managed-url",
    "set-in-local-env-only",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                raw = str(match.group(2) or "").strip()
                for delimiter in ('"', "'", ",", "]", "}", ";"):
                    raw = raw.split(delimiter, 1)[0]
                normalized = raw.strip().strip("<>").lower()
                if normalized in SAFE_SECRET_PLACEHOLDERS:
                    continue
            return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(_redact(key)): _redact(item) for key, item in value.items()}
    return value


def _safe_text(value: Any) -> str:
    text = str(value or "")
    redacted = _redact(text)
    return redacted if isinstance(redacted, str) else str(redacted)


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item) for item in value]


def _json_sort_key(path: Path) -> tuple[str, float, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
    return generated_at, path.stat().st_mtime, path.name


def _latest_json(directory: Path) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob("*.json") if item.is_file()]
    return max(files, key=_json_sort_key) if files else None


def _latest_usable_business_smoke_json(directory: Path) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    candidates: list[Path] = []
    for path in directory.glob("*.json"):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        env_profile = payload.get("env_profile") if isinstance(payload.get("env_profile"), dict) else {}
        real_read_smoke = (
            payload.get("demo_business_system_used") is not True
            and payload.get("real_business_system_connected") is not False
            and env_profile.get("public_production_gap") is not True
        )
        if (
            payload.get("status") == "success"
            and payload.get("business_system_connected") is True
            and payload.get("business_read_executed") is True
            and payload.get("business_write_executed") is False
            and payload.get("business_data_written") is False
            and payload.get("local_business_mock_used") is not True
            and payload.get("secret_plaintext_output") is not True
            and (
                payload.get("demo_business_system_used") is True
                or payload.get("real_business_system_connected") is True
                or real_read_smoke
            )
        ):
            candidates.append(path)
    return max(candidates, key=_json_sort_key) if candidates else None


def _read_source(source_id: str, directory: Path) -> dict[str, Any]:
    latest = (
        _latest_usable_business_smoke_json(directory)
        if source_id == "business_system_read_smoke"
        else _latest_json(directory)
    )
    if latest is None:
        return {
            "source_id": source_id,
            "present": False,
            "status": "missing",
            "generated_at": "",
            "latest_json_path": "",
            "payload": {},
            "summary": {},
            "missing_conditions": [f"{source_id}:latest_report_missing"],
            "secret_detected": False,
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "source_id": source_id,
            "present": True,
            "status": "blocked",
            "generated_at": "",
            "latest_json_path": _safe_text(latest),
            "payload": {},
            "summary": {},
            "missing_conditions": [f"{source_id}:json_parse_failed"],
            "secret_detected": False,
        }
    if not isinstance(payload, dict):
        payload = {}
    secret_detected = _contains_secret_like(payload)
    safe_payload = {} if secret_detected else payload
    missing = _safe_string_list(payload.get("missing_conditions"))[:24]
    if secret_detected:
        missing.append(f"{source_id}:secret_like_text_detected")
    return {
        "source_id": source_id,
        "present": True,
        "status": "blocked" if secret_detected else str(payload.get("status") or "skipped"),
        "generated_at": _safe_text(payload.get("generated_at") or ""),
        "latest_json_path": _safe_text(latest),
        "payload": safe_payload,
        "summary": _source_summary(source_id, safe_payload),
        "missing_conditions": sorted(set(missing)),
        "secret_detected": secret_detected,
    }


def _source_summary(source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if source_id == "controlled_pilot_delivery_gate":
        return {
            "controlled_pilot_delivery_ready": payload.get("controlled_pilot_delivery_ready"),
            "enterprise_landing_scope": payload.get("enterprise_landing_scope"),
            "accepted_remaining_gaps": _safe_string_list(payload.get("accepted_remaining_gaps")),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "controlled_pilot_launch_gate":
        return {
            "ready_for_controlled_pilot": payload.get("ready_for_controlled_pilot"),
            "controlled_pilot": payload.get("controlled_pilot"),
            "accepted_remaining_gaps": _safe_string_list(payload.get("accepted_remaining_gaps")),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "controlled_pilot_launch_package":
        window = payload.get("launch_window") if isinstance(payload.get("launch_window"), dict) else {}
        return {
            "launch_package_ready": payload.get("launch_package_ready"),
            "controlled_pilot": payload.get("controlled_pilot"),
            "accepted_remaining_gaps": _safe_string_list(payload.get("accepted_remaining_gaps")),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "rollback_required": window.get("rollback_required"),
            "external_expansion_requires_new_manual_go_no_go": window.get(
                "external_expansion_requires_new_manual_go_no_go"
            ),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id in {"controlled_pilot_status_summary", "controlled_pilot_operator_packet"}:
        return {
            "controlled_internal_pilot": payload.get("controlled_internal_pilot"),
            "accepted_remaining_gaps": _safe_string_list(payload.get("accepted_remaining_gaps")),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "controlled_pilot_console_verify":
        return {
            "controlled_internal_pilot": payload.get("controlled_internal_pilot"),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "production_landing_refresh_status":
        return {
            "final_status": payload.get("final_status"),
            "blocker_count": payload.get("blocker_count"),
            "final_blockers": _safe_string_list(payload.get("final_blockers")),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "production_landing_status":
        real_llm = payload.get("real_llm") if isinstance(payload.get("real_llm"), dict) else {}
        return {
            "execution_allowed": payload.get("execution_allowed"),
            "ready_domain_count": payload.get("ready_domain_count"),
            "domain_count": payload.get("domain_count"),
            "blockers": _safe_string_list(payload.get("blockers")),
            "real_llm_status": real_llm.get("status"),
            "real_llm_executed": real_llm.get("real_llm_executed"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "business_system_read_smoke":
        return {
            "business_system_connected": payload.get("business_system_connected"),
            "business_read_executed": payload.get("business_read_executed"),
            "business_write_executed": payload.get("business_write_executed"),
            "business_data_written": payload.get("business_data_written"),
            "local_business_mock_used": payload.get("local_business_mock_used"),
            "demo_business_system_used": payload.get("demo_business_system_used"),
            "real_business_system_connected": payload.get("real_business_system_connected"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    return {}


def _source_payload(sources: dict[str, dict[str, Any]], source_id: str) -> dict[str, Any]:
    payload = sources.get(source_id, {}).get("payload")
    return payload if isinstance(payload, dict) else {}


def _accepted_gaps_from_sources(sources: dict[str, dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for source_id in (
        "controlled_pilot_delivery_gate",
        "controlled_pilot_launch_gate",
        "controlled_pilot_launch_package",
        "controlled_pilot_status_summary",
        "controlled_pilot_operator_packet",
    ):
        payload = _source_payload(sources, source_id)
        gaps.extend(_safe_string_list(payload.get("accepted_remaining_gaps")))
    refresh = _source_payload(sources, "production_landing_refresh_status")
    gaps.extend(_safe_string_list(refresh.get("final_blockers")))
    landing = _source_payload(sources, "production_landing_status")
    gaps.extend(_safe_string_list(landing.get("blockers")))
    return sorted(set(item for item in gaps if item))


def _demo_business_read_ready(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("status") == "success"
        and payload.get("business_system_connected") is True
        and payload.get("business_read_executed") is True
        and payload.get("business_write_executed") is False
        and payload.get("business_data_written") is False
        and payload.get("local_business_mock_used") is False
        and payload.get("demo_business_system_used") is True
        and payload.get("real_business_system_connected") is not True
    )


def _derive_packet(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing_conditions: list[str] = []
    for source_id in REQUIRED_SOURCES:
        source = sources[source_id]
        if source.get("present") is not True:
            missing_conditions.append(f"{source_id}:latest_report_missing")
        if source.get("secret_detected") is True:
            missing_conditions.append(f"{source_id}:secret_like_text_detected")
        if source.get("status") in {"blocked", "failed", "missing"}:
            missing_conditions.append(f"{source_id}:not_usable")
        for condition in source.get("missing_conditions", []):
            if condition:
                missing_conditions.append(f"{source_id}:{condition}")

    delivery = _source_payload(sources, "controlled_pilot_delivery_gate")
    launch_gate = _source_payload(sources, "controlled_pilot_launch_gate")
    launch_package = _source_payload(sources, "controlled_pilot_launch_package")
    status_summary = _source_payload(sources, "controlled_pilot_status_summary")
    operator_packet = _source_payload(sources, "controlled_pilot_operator_packet")
    console_verify = _source_payload(sources, "controlled_pilot_console_verify")
    refresh_status = _source_payload(sources, "production_landing_refresh_status")
    landing_status = _source_payload(sources, "production_landing_status")
    business_smoke = _source_payload(sources, "business_system_read_smoke")

    public_values = [
        payload.get("public_production_direct_launch")
        for payload in (
            delivery,
            launch_gate,
            launch_package,
            status_summary,
            operator_packet,
            console_verify,
            refresh_status,
            landing_status,
            business_smoke,
        )
    ]
    if not all(str(value or "No-Go") == "No-Go" for value in public_values):
        missing_conditions.append("controlled_pilot_run_packet:public_production_boundary_changed")

    accepted_gaps = _accepted_gaps_from_sources(sources)
    unexpected_gaps = sorted(set(accepted_gaps) - ACCEPTED_REMAINING_GAPS)
    if unexpected_gaps:
        missing_conditions.extend(f"controlled_pilot_run_packet:unexpected_gap:{gap}" for gap in unexpected_gaps)

    expected_gap_present = accepted_gaps == ["business_system:real_business_system_required"]
    if not expected_gap_present:
        missing_conditions.append("controlled_pilot_run_packet:accepted_business_gap_not_declared")

    ready_checks = [
        delivery.get("status") == "success",
        delivery.get("controlled_pilot_delivery_ready") is True,
        delivery.get("enterprise_landing_scope") == READY_SCOPE,
        int(delivery.get("missing_condition_count") or 0) == 0,
        launch_gate.get("status") == "ready",
        launch_gate.get("ready_for_controlled_pilot") is True,
        launch_gate.get("controlled_pilot") == "Go",
        int(launch_gate.get("missing_condition_count") or 0) == 0,
        launch_package.get("status") == "ready",
        launch_package.get("launch_package_ready") is True,
        launch_package.get("controlled_pilot") == "Go",
        int(launch_package.get("missing_condition_count") or 0) == 0,
        status_summary.get("status") == "ready",
        status_summary.get("controlled_internal_pilot") == "Go",
        operator_packet.get("status") == "ready",
        operator_packet.get("controlled_internal_pilot") == "Go",
        console_verify.get("status") == "success",
        console_verify.get("controlled_internal_pilot") == "Go",
        int(console_verify.get("missing_condition_count") or 0) == 0,
        refresh_status.get("status") == "partial",
        refresh_status.get("final_blockers") == ["business_system:real_business_system_required"],
        landing_status.get("status") == "partial",
        landing_status.get("blockers") == ["business_system:real_business_system_required"],
        landing_status.get("execution_allowed") is True,
        _demo_business_read_ready(business_smoke),
    ]
    if not all(ready_checks):
        missing_conditions.append("controlled_pilot_run_packet:required_ready_evidence_not_satisfied")

    secret_plaintext_output = any(
        source.get("secret_detected") is True
        or _source_payload(sources, source_id).get("secret_plaintext_output") is True
        for source_id, source in sources.items()
    )
    if secret_plaintext_output:
        missing_conditions.append("controlled_pilot_run_packet:secret_plaintext_output_detected")

    launch_window = launch_package.get("launch_window") if isinstance(launch_package.get("launch_window"), dict) else {}
    rollback_required = launch_window.get("rollback_required") is True or operator_packet.get("rollback_required") is True
    expansion_requires_review = (
        launch_window.get("external_expansion_requires_new_manual_go_no_go") is True
        or operator_packet.get("external_expansion_requires_new_manual_go_no_go") is True
    )
    if not rollback_required:
        missing_conditions.append("controlled_pilot_run_packet:rollback_not_required")
    if not expansion_requires_review:
        missing_conditions.append("controlled_pilot_run_packet:external_expansion_review_not_required")

    ready = not missing_conditions and not secret_plaintext_output
    status = "ready" if ready else ("blocked" if secret_plaintext_output or any("public_production_boundary" in item for item in missing_conditions) else "partial")

    operator_commands = {
        "verify_console": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_console_verify.ps1",
        "refresh_status": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 scripts\\production_landing_refresh_status.py --env-path local\\production_landing.staging.env",
        "refresh_run_packet": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 scripts\\controlled_pilot_run_packet.py",
        "rollback_console": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_console_down.ps1",
    }
    return {
        "status": status,
        "run_packet_ready": ready,
        "controlled_internal_pilot": "Go" if ready else ("No-Go" if status == "blocked" else "Manual-Review"),
        "ready_scope": READY_SCOPE,
        "public_production_direct_launch": "No-Go",
        "accepted_remaining_gaps": accepted_gaps,
        "real_production_remaining_gaps": ["business_system:real_business_system_required"],
        "business_system_boundary": {
            "connected": bool(business_smoke.get("business_system_connected", False)),
            "read_executed": bool(business_smoke.get("business_read_executed", False)),
            "write_executed": bool(business_smoke.get("business_write_executed", False)),
            "business_data_written": bool(business_smoke.get("business_data_written", False)),
            "local_business_mock_used": bool(business_smoke.get("local_business_mock_used", False)),
            "demo_business_system_used": bool(business_smoke.get("demo_business_system_used", False)),
            "real_business_system_connected": bool(business_smoke.get("real_business_system_connected", False)),
        },
        "safety_boundary": {
            "read_only": True,
            "manual_signoff_required": True,
            "rollback_required": rollback_required,
            "external_expansion_requires_new_manual_go_no_go": expansion_requires_review,
            "public_production_direct_launch": "No-Go",
            "business_data_written": False,
            "audit_data_written": False,
            "metrics_data_written": False,
            "auto_approved": False,
            "auto_closed": False,
        },
        "operator_commands": operator_commands,
        "evidence_paths": {
            source_id: _safe_text(source.get("latest_json_path") or "") for source_id, source in sources.items()
        },
        "source_statuses": {source_id: _safe_text(source.get("status") or "") for source_id, source in sources.items()},
        "missing_conditions": sorted(set(missing_conditions)),
        "missing_condition_count": len(set(missing_conditions)),
        "secret_plaintext_output": secret_plaintext_output,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 受控内网试点运行包",
        "",
        f"- status: {payload.get('status', '')}",
        f"- run_packet_ready: {payload.get('run_packet_ready', False)}",
        f"- controlled_internal_pilot: {payload.get('controlled_internal_pilot', '')}",
        f"- ready_scope: {payload.get('ready_scope', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- missing_condition_count: {payload.get('missing_condition_count', 0)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 接受的剩余缺口",
    ]
    accepted = payload.get("accepted_remaining_gaps", [])
    lines.extend(f"- {item}" for item in accepted) if accepted else lines.append("- none")
    lines.extend(["", "## 真实生产剩余缺口"])
    gaps = payload.get("real_production_remaining_gaps", [])
    lines.extend(f"- {item}" for item in gaps) if gaps else lines.append("- none")
    lines.extend(["", "## 操作命令"])
    for key, command in payload.get("operator_commands", {}).items():
        lines.append(f"- {key}: `{command}`")
    lines.extend(["", "## 证据路径"])
    for source_id, path in payload.get("evidence_paths", {}).items():
        lines.append(f"- {source_id}: `{path}`")
    lines.extend(["", "## 缺失条件"])
    missing = payload.get("missing_conditions", [])
    lines.extend(f"- {item}" for item in missing) if missing else lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def build_controlled_pilot_run_packet(
    *,
    output_dir: str | Path | None = None,
    source_dirs: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    effective_dirs = {
        source_id: Path(source_dirs[source_id]) if source_dirs and source_id in source_dirs else directory
        for source_id, directory in SOURCE_DIRS.items()
    }
    sources = {source_id: _read_source(source_id, directory) for source_id, directory in effective_dirs.items()}
    packet = _derive_packet(sources)
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.9.8",
        "phase": "v4.9 Controlled Pilot Run Packet",
        "mode": "read_only_controlled_pilot_run_packet",
        "read_only": True,
        "sources": {
            source_id: {
                "present": source["present"],
                "status": source["status"],
                "generated_at": source["generated_at"],
                "latest_json_path": source["latest_json_path"],
                "summary": source["summary"],
                "missing_conditions": source["missing_conditions"],
                "secret_detected": source["secret_detected"],
            }
            for source_id, source in sources.items()
        },
        **packet,
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["run_packet_ready"] = False
        payload["controlled_internal_pilot"] = "No-Go"
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"] = sorted(
            set([*payload["missing_conditions"], "controlled_pilot_run_packet:secret_like_text_detected"])
        )
        payload["missing_condition_count"] = len(payload["missing_conditions"])
        payload = _redact(payload)

    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not output_root.is_absolute():
        output_root = ROOT_DIR / output_root
    output_root.mkdir(parents=True, exist_ok=True)
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_run_packet"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(markdown_path)
    payload["output_dir"] = str(output_root)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "run_packet_ready": bool(payload["run_packet_ready"]),
        "controlled_internal_pilot": payload["controlled_internal_pilot"],
        "public_production_direct_launch": payload["public_production_direct_launch"],
        "missing_condition_count": int(payload["missing_condition_count"]),
        "secret_plaintext_output": bool(payload["secret_plaintext_output"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only controlled internal pilot run packet.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    summary = build_controlled_pilot_run_packet(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
