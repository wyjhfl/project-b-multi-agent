from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "operations_console_landing_smoke"
DEFAULT_FRONTEND_URL = "http://127.0.0.1:3002"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
PAGE_REQUIRED_MARKERS = [
    "受控试点总状态摘要",
    "受控试点操作员交接包",
    "controlled_internal_pilot",
    "public_production_direct_launch",
    "blocking_reports",
    "rollback_required",
    "source",
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(token|api[_-]?key|password|client[_-]?secret|jwt[_-]?secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items()}
    return value


def _safe_url(value: str) -> str:
    text = (value or "").strip().rstrip("/")
    return _redact(text) if isinstance(_redact(text), str) else ""


def _http_get_text(url: str, timeout_seconds: float) -> tuple[int | None, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "project-b-operations-console-smoke"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(256_000).decode("utf-8", errors="replace")
            return int(response.status), body, ""
    except urllib.error.HTTPError as exc:
        body = exc.read(16_000).decode("utf-8", errors="replace")
        return int(exc.code), body, exc.__class__.__name__
    except Exception as exc:
        return None, "", exc.__class__.__name__


def _http_get_json(url: str, timeout_seconds: float) -> tuple[int | None, dict[str, Any], str]:
    status, body, error = _http_get_text(url, timeout_seconds)
    if status is None:
        return status, {}, error
    try:
        payload = json.loads(body)
    except Exception as exc:
        return status, {}, f"json_parse_failed:{exc.__class__.__name__}"
    return status, payload if isinstance(payload, dict) else {}, error


def _expected_summary_fields(payload: dict[str, Any]) -> dict[str, Any]:
    observability = payload.get("observability") if isinstance(payload.get("observability"), dict) else {}
    preflight = observability.get("production_landing_xiaomi_llm_preflight")
    blocker = observability.get("production_landing_blocker_resolution")
    pilot_bundle = observability.get("production_pilot_evidence_bundle")
    controlled_status = observability.get("controlled_pilot_status_summary")
    operator_packet = observability.get("controlled_pilot_operator_packet")
    launch_gate = observability.get("controlled_pilot_launch_gate")
    launch_package = observability.get("controlled_pilot_launch_package")
    window_record = observability.get("controlled_pilot_window_record")
    window_status = observability.get("controlled_pilot_window_status")
    preflight = preflight if isinstance(preflight, dict) else {}
    blocker = blocker if isinstance(blocker, dict) else {}
    pilot_bundle = pilot_bundle if isinstance(pilot_bundle, dict) else {}
    controlled_status = controlled_status if isinstance(controlled_status, dict) else {}
    operator_packet = operator_packet if isinstance(operator_packet, dict) else {}
    launch_gate = launch_gate if isinstance(launch_gate, dict) else {}
    launch_package = launch_package if isinstance(launch_package, dict) else {}
    window_record = window_record if isinstance(window_record, dict) else {}
    window_status = window_status if isinstance(window_status, dict) else {}
    window_status_window = window_status.get("window") if isinstance(window_status.get("window"), dict) else {}
    window_status_operations = (
        window_status.get("operations_summary") if isinstance(window_status.get("operations_summary"), dict) else {}
    )
    actions = blocker.get("actions") if isinstance(blocker.get("actions"), list) else []
    llm_action = next(
        (item for item in actions if isinstance(item, dict) and item.get("action_id") == "real_llm_preflight"),
        {},
    )
    evidence = llm_action.get("evidence") if isinstance(llm_action.get("evidence"), dict) else {}
    acceptance_blockers = preflight.get("acceptance_blockers") if isinstance(preflight.get("acceptance_blockers"), list) else []
    evidence_blockers = evidence.get("acceptance_blockers") if isinstance(evidence.get("acceptance_blockers"), list) else []
    missing_conditions: list[str] = []
    if "network_check_requested" not in preflight:
        missing_conditions.append("operations_summary:xiaomi_preflight_network_check_requested_missing")
    if "network_check_allowed" not in preflight:
        missing_conditions.append("operations_summary:xiaomi_preflight_network_check_allowed_missing")
    if "safe_next_action" not in preflight:
        missing_conditions.append("operations_summary:xiaomi_preflight_safe_next_action_missing")
    if "acceptance_blockers" not in preflight:
        missing_conditions.append("operations_summary:xiaomi_preflight_acceptance_blockers_missing")
    if evidence and "safe_next_action" not in evidence:
        missing_conditions.append("operations_summary:blocker_resolution_safe_next_action_missing")
    if evidence and "acceptance_blockers" not in evidence:
        missing_conditions.append("operations_summary:blocker_resolution_acceptance_blockers_missing")
    for field in [
        "status",
        "controlled_pilot_ready",
        "controlled_pilot",
        "final_verification_passed_count",
        "final_verification_requirement_count",
        "missing_condition_count",
        "public_production_direct_launch",
        "secret_plaintext_output",
    ]:
        if field not in pilot_bundle:
            missing_conditions.append(f"operations_summary:pilot_evidence_bundle_{field}_missing")
    if pilot_bundle and pilot_bundle.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("operations_summary:pilot_evidence_bundle_public_direct_launch_not_no_go")
    for field in [
        "status",
        "controlled_internal_pilot",
        "public_production_direct_launch",
        "secret_plaintext_output",
        "blocking_reports",
        "source_statuses",
        "operations_console_smoke_execute",
        "runtime_smoke_passed",
    ]:
        if field not in controlled_status:
            missing_conditions.append(f"operations_summary:controlled_pilot_status_summary_{field}_missing")
    if controlled_status and controlled_status.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("operations_summary:controlled_pilot_status_summary_public_direct_launch_not_no_go")
    for field in [
        "status",
        "controlled_internal_pilot",
        "public_production_direct_launch",
        "window_id",
        "latest_report_present",
        "rollback_required",
        "external_expansion_requires_new_manual_go_no_go",
        "secret_plaintext_output",
    ]:
        if field not in operator_packet:
            missing_conditions.append(f"operations_summary:controlled_pilot_operator_packet_{field}_missing")
    if operator_packet and operator_packet.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("operations_summary:controlled_pilot_operator_packet_public_direct_launch_not_no_go")
    for field in [
        "status",
        "ready_for_controlled_pilot",
        "controlled_pilot",
        "public_production_direct_launch",
        "secret_plaintext_output",
    ]:
        if field not in launch_gate:
            missing_conditions.append(f"operations_summary:controlled_pilot_launch_gate_{field}_missing")
    if launch_gate and launch_gate.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("operations_summary:controlled_pilot_launch_gate_public_direct_launch_not_no_go")
    for field in [
        "status",
        "launch_package_ready",
        "controlled_pilot",
        "public_production_direct_launch",
        "secret_plaintext_output",
    ]:
        if field not in launch_package:
            missing_conditions.append(f"operations_summary:controlled_pilot_launch_package_{field}_missing")
    if launch_package and launch_package.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("operations_summary:controlled_pilot_launch_package_public_direct_launch_not_no_go")
    for field in [
        "status",
        "opened",
        "window_id",
        "public_production_direct_launch",
        "secret_plaintext_output",
    ]:
        if field not in window_record:
            missing_conditions.append(f"operations_summary:controlled_pilot_window_record_{field}_missing")
    if window_record and window_record.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("operations_summary:controlled_pilot_window_record_public_direct_launch_not_no_go")
    for field in [
        "status",
        "window",
        "operations_summary",
        "public_production_direct_launch",
        "secret_plaintext_output",
    ]:
        if field not in window_status:
            missing_conditions.append(f"operations_summary:controlled_pilot_window_status_{field}_missing")
    if window_status and window_status.get("public_production_direct_launch") != "No-Go":
        missing_conditions.append("operations_summary:controlled_pilot_window_status_public_direct_launch_not_no_go")
    return {
        "missing_conditions": missing_conditions,
        "preflight_status": str(preflight.get("status") or ""),
        "network_check_requested": bool(preflight.get("network_check_requested", False)),
        "network_check_allowed": bool(preflight.get("network_check_allowed", False)),
        "safe_next_action": str(preflight.get("safe_next_action") or ""),
        "acceptance_blockers": [str(item) for item in acceptance_blockers[:12]],
        "blocker_action_present": bool(evidence),
        "blocker_safe_next_action": str(evidence.get("safe_next_action") or ""),
        "blocker_acceptance_blockers": [str(item) for item in evidence_blockers[:12]],
        "pilot_evidence_status": str(pilot_bundle.get("status") or ""),
        "pilot_evidence_controlled_pilot_ready": bool(pilot_bundle.get("controlled_pilot_ready", False)),
        "pilot_evidence_controlled_pilot": str(pilot_bundle.get("controlled_pilot") or ""),
        "pilot_evidence_final_verification_passed_count": int(
            pilot_bundle.get("final_verification_passed_count") or 0
        ),
        "pilot_evidence_final_verification_requirement_count": int(
            pilot_bundle.get("final_verification_requirement_count") or 0
        ),
        "pilot_evidence_missing_condition_count": int(pilot_bundle.get("missing_condition_count") or 0),
        "pilot_evidence_public_production_direct_launch": str(
            pilot_bundle.get("public_production_direct_launch") or ""
        ),
        "pilot_evidence_secret_plaintext_output": bool(pilot_bundle.get("secret_plaintext_output", False)),
        "controlled_status_status": str(controlled_status.get("status") or ""),
        "controlled_status_internal_pilot": str(controlled_status.get("controlled_internal_pilot") or ""),
        "controlled_status_public_production_direct_launch": str(
            controlled_status.get("public_production_direct_launch") or ""
        ),
        "controlled_status_secret_plaintext_output": bool(controlled_status.get("secret_plaintext_output", False)),
        "controlled_status_blocking_report_count": len(
            controlled_status.get("blocking_reports") if isinstance(controlled_status.get("blocking_reports"), list) else []
        ),
        "controlled_status_source_status_count": len(
            controlled_status.get("source_statuses") if isinstance(controlled_status.get("source_statuses"), dict) else {}
        ),
        "controlled_status_operations_console_smoke_execute": bool(
            controlled_status.get("operations_console_smoke_execute", False)
        ),
        "controlled_status_runtime_smoke_passed": bool(controlled_status.get("runtime_smoke_passed", False)),
        "operator_packet_status": str(operator_packet.get("status") or ""),
        "operator_packet_internal_pilot": str(operator_packet.get("controlled_internal_pilot") or ""),
        "operator_packet_public_production_direct_launch": str(
            operator_packet.get("public_production_direct_launch") or ""
        ),
        "operator_packet_window_id": str(operator_packet.get("window_id") or ""),
        "operator_packet_latest_report_present": bool(operator_packet.get("latest_report_present", False)),
        "operator_packet_rollback_required": bool(operator_packet.get("rollback_required", False)),
        "operator_packet_external_expansion_requires_new_manual_go_no_go": bool(
            operator_packet.get("external_expansion_requires_new_manual_go_no_go", False)
        ),
        "operator_packet_secret_plaintext_output": bool(operator_packet.get("secret_plaintext_output", False)),
        "launch_gate_status": str(launch_gate.get("status") or ""),
        "launch_gate_ready": bool(launch_gate.get("ready_for_controlled_pilot", False)),
        "launch_gate_controlled_pilot": str(launch_gate.get("controlled_pilot") or ""),
        "launch_gate_public_production_direct_launch": str(launch_gate.get("public_production_direct_launch") or ""),
        "launch_gate_secret_plaintext_output": bool(launch_gate.get("secret_plaintext_output", False)),
        "launch_package_status": str(launch_package.get("status") or ""),
        "launch_package_ready": bool(launch_package.get("launch_package_ready", False)),
        "launch_package_controlled_pilot": str(launch_package.get("controlled_pilot") or ""),
        "launch_package_public_production_direct_launch": str(
            launch_package.get("public_production_direct_launch") or ""
        ),
        "launch_package_secret_plaintext_output": bool(launch_package.get("secret_plaintext_output", False)),
        "window_record_status": str(window_record.get("status") or ""),
        "window_record_opened": bool(window_record.get("opened", False)),
        "window_record_id": str(window_record.get("window_id") or ""),
        "window_record_public_production_direct_launch": str(
            window_record.get("public_production_direct_launch") or ""
        ),
        "window_record_secret_plaintext_output": bool(window_record.get("secret_plaintext_output", False)),
        "window_status_status": str(window_status.get("status") or ""),
        "window_status_opened": bool(window_status_window.get("opened", False)),
        "window_status_window_id": str(window_status_window.get("window_id") or ""),
        "window_status_health_status": str(window_status_operations.get("health_status") or ""),
        "window_status_deployment_ok": bool(window_status_operations.get("deployment_ok", False)),
        "window_status_public_production_direct_launch": str(
            window_status.get("public_production_direct_launch") or ""
        ),
        "window_status_secret_plaintext_output": bool(window_status.get("secret_plaintext_output", False)),
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    checks = payload.get("checks", {}) if isinstance(payload.get("checks"), dict) else {}
    lines = [
        "# Operations Console Landing Smoke",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execute: {payload.get('execute', False)}",
        f"- frontend_url: {payload.get('frontend_url', '')}",
        f"- backend_url: {payload.get('backend_url', '')}",
        f"- page_http_status: {checks.get('page_http_status')}",
        f"- summary_http_status: {checks.get('summary_http_status')}",
        f"- safe_next_action: {checks.get('safe_next_action', '')}",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## Missing Conditions",
    ]
    lines.extend(f"- {item}" for item in payload.get("missing_conditions", []))
    lines.append("")
    return "\n".join(lines)


def build_operations_console_landing_smoke(
    *,
    output_dir: str | Path | None = None,
    execute: bool = False,
    frontend_url: str = DEFAULT_FRONTEND_URL,
    backend_url: str = DEFAULT_BACKEND_URL,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    if _contains_secret_like(commit):
        commit = "redacted"

    safe_frontend_url = _safe_url(frontend_url)
    safe_backend_url = _safe_url(backend_url)
    missing_conditions: list[str] = []
    checks: dict[str, Any] = {
        "page_http_status": None,
        "summary_http_status": None,
        "backend_summary_http_status": None,
        "preflight_status": "",
        "network_check_requested": False,
        "network_check_allowed": False,
        "safe_next_action": "",
        "acceptance_blockers": [],
        "blocker_action_present": False,
        "blocker_safe_next_action": "",
        "blocker_acceptance_blockers": [],
        "pilot_evidence_status": "",
        "pilot_evidence_controlled_pilot_ready": False,
        "pilot_evidence_controlled_pilot": "",
        "pilot_evidence_final_verification_passed_count": 0,
        "pilot_evidence_final_verification_requirement_count": 0,
        "pilot_evidence_missing_condition_count": 0,
        "pilot_evidence_public_production_direct_launch": "",
        "pilot_evidence_secret_plaintext_output": False,
        "controlled_status_status": "",
        "controlled_status_internal_pilot": "",
        "controlled_status_public_production_direct_launch": "",
        "controlled_status_secret_plaintext_output": False,
        "controlled_status_blocking_report_count": 0,
        "controlled_status_source_status_count": 0,
        "controlled_status_operations_console_smoke_execute": False,
        "controlled_status_runtime_smoke_passed": False,
        "operator_packet_status": "",
        "operator_packet_internal_pilot": "",
        "operator_packet_public_production_direct_launch": "",
        "operator_packet_window_id": "",
        "operator_packet_latest_report_present": False,
        "operator_packet_rollback_required": False,
        "operator_packet_external_expansion_requires_new_manual_go_no_go": False,
        "operator_packet_secret_plaintext_output": False,
        "launch_gate_status": "",
        "launch_gate_ready": False,
        "launch_gate_controlled_pilot": "",
        "launch_gate_public_production_direct_launch": "",
        "launch_gate_secret_plaintext_output": False,
        "launch_package_status": "",
        "launch_package_ready": False,
        "launch_package_controlled_pilot": "",
        "launch_package_public_production_direct_launch": "",
        "launch_package_secret_plaintext_output": False,
        "window_record_status": "",
        "window_record_opened": False,
        "window_record_id": "",
        "window_record_public_production_direct_launch": "",
        "window_record_secret_plaintext_output": False,
        "window_status_status": "",
        "window_status_opened": False,
        "window_status_window_id": "",
        "window_status_health_status": "",
        "window_status_deployment_ok": False,
        "window_status_public_production_direct_launch": "",
        "window_status_secret_plaintext_output": False,
        "page_contains_operations_marker": False,
        "page_required_markers_present": False,
        "page_missing_markers": [],
    }

    if not execute:
        status = "skipped"
        missing_conditions.append("cli:--execute_not_requested")
    else:
        page_status, page_body, page_error = _http_get_text(f"{safe_frontend_url}/operations", timeout_seconds)
        summary_status, summary_payload, summary_error = _http_get_json(
            f"{safe_frontend_url}/api/operations/summary",
            timeout_seconds,
        )
        backend_status, backend_payload, backend_error = _http_get_json(
            f"{safe_backend_url}/operations/summary",
            timeout_seconds,
        )
        checks.update(
            {
                "page_http_status": page_status,
                "summary_http_status": summary_status,
                "backend_summary_http_status": backend_status,
                "page_error": page_error,
                "summary_error": summary_error,
                "backend_summary_error": backend_error,
                "page_contains_operations_marker": "Operations" in page_body or "operations" in page_body.lower(),
                "page_required_markers_present": all(marker in page_body for marker in PAGE_REQUIRED_MARKERS),
                "page_missing_markers": [marker for marker in PAGE_REQUIRED_MARKERS if marker not in page_body],
            }
        )
        if page_status != 200:
            missing_conditions.append("operations_page:http_status_not_200")
        if page_status == 200 and checks["page_contains_operations_marker"] is not True:
            missing_conditions.append("operations_page:operations_marker_missing")
        if page_status == 200 and checks["page_required_markers_present"] is not True:
            missing_conditions.append("operations_page:controlled_pilot_status_markers_missing")
        if summary_status != 200:
            missing_conditions.append("operations_summary_proxy:http_status_not_200")
        if backend_status != 200:
            missing_conditions.append("operations_summary_backend:http_status_not_200")
        summary_fields = _expected_summary_fields(summary_payload)
        checks.update(summary_fields)
        missing_conditions.extend(summary_fields["missing_conditions"])
        status = "success" if not missing_conditions else "failed"
        if backend_status == 200 and summary_status != 200:
            status = "partial"

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.4",
        "phase": "v4.8 Operations Console Landing Smoke",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "mode": "read_only_operations_console_smoke",
        "execute": execute,
        "frontend_url": safe_frontend_url,
        "backend_url": safe_backend_url,
        "checks": _redact(checks),
        "missing_conditions": sorted(set(missing_conditions)),
        "real_llm_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
        "output_dir": str(output_root),
    }
    if _contains_secret_like(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = True
        payload["missing_conditions"] = sorted(set([*payload["missing_conditions"], "output:secret_like_text_detected"]))

    short_commit = commit[:8] if commit != "unknown" else "unknown"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_operations_console_landing_smoke"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "execute": execute,
        "page_http_status": payload["checks"]["page_http_status"],
        "summary_http_status": payload["checks"]["summary_http_status"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Operations console landing fields through the frontend proxy.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_operations_console_landing_smoke(
        output_dir=args.output_dir,
        execute=args.execute,
        frontend_url=args.frontend_url,
        backend_url=args.backend_url,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
