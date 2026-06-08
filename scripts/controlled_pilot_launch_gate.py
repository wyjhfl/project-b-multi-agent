from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_gate"
STATUS_VOCABULARY = ["ready", "blocked"]

SOURCE_DIRS = {
    "controlled_pilot_delivery_gate": ROOT_DIR / "docs" / "reports" / "controlled_pilot_delivery_gate",
    "production_pilot_evidence_bundle": ROOT_DIR / "docs" / "reports" / "production_pilot_evidence_bundle",
    "production_landing_final_verification": ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
    "production_landing_signoff_closeout": ROOT_DIR / "docs" / "reports" / "production_landing_signoff_closeout",
    "production_pilot_bootstrap": ROOT_DIR / "docs" / "reports" / "production_pilot_bootstrap",
}

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
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    lowered = text.lower()
    for marker in ("sk-", "tp-", "bearer ", "postgresql://", "postgres://", "redis://"):
        if marker in lowered:
            return True
    for marker in ("api_key=", "apikey=", "token=", "password=", "client_secret=", "jwt_secret="):
        start = 0
        while True:
            index = lowered.find(marker, start)
            if index < 0:
                break
            raw_tail = text[index + len(marker) :]
            raw_value = ""
            for char in raw_tail:
                if char.isspace() or char in {",", "]", "}", "\"", "'", ";", "|"}:
                    break
                raw_value += char
            normalized = raw_value.strip("<>").lower()
            if normalized and normalized not in SAFE_SECRET_PLACEHOLDERS:
                return True
            start = index + len(marker)
    return False


def _safe_text(value: Any) -> str:
    text = str(value or "")
    return "[redacted-secret-like-text]" if _contains_secret_like(text) else text


def _json_report_sort_key(path: Path) -> tuple[str, float, str]:
    generated_at = ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            generated_at = str(payload.get("generated_at") or "")
    except Exception:
        generated_at = ""
    return generated_at, path.stat().st_mtime, path.name


def _latest_json(directory: Path) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob("*.json") if item.is_file()]
    return max(files, key=_json_report_sort_key) if files else None


def _read_latest_source(source_id: str, directory: Path) -> dict[str, Any]:
    latest = _latest_json(directory)
    if latest is None:
        return {
            "source_id": source_id,
            "present": False,
            "status": "skipped",
            "latest_json_path": "",
            "generated_at": "",
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
            "latest_json_path": _safe_text(latest),
            "generated_at": "",
            "summary": {},
            "missing_conditions": [f"{source_id}:json_parse_failed"],
            "secret_detected": False,
        }

    missing = payload.get("missing_conditions") if isinstance(payload.get("missing_conditions"), list) else []
    return {
        "source_id": source_id,
        "present": True,
        "status": _safe_text(payload.get("status") or "skipped"),
        "latest_json_path": _safe_text(latest),
        "generated_at": _safe_text(payload.get("generated_at") or ""),
        "summary": _source_summary(source_id, payload),
        "missing_conditions": [_safe_text(item) for item in missing[:16]],
        "secret_detected": _contains_secret_like(payload),
    }


def _source_summary(source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if source_id == "controlled_pilot_delivery_gate":
        return {
            "controlled_pilot_delivery_ready": payload.get("controlled_pilot_delivery_ready"),
            "enterprise_landing_scope": payload.get("enterprise_landing_scope"),
            "accepted_remaining_gaps": payload.get("accepted_remaining_gaps")
            if isinstance(payload.get("accepted_remaining_gaps"), list)
            else [],
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
            "auto_approved": payload.get("auto_approved"),
            "auto_closed": payload.get("auto_closed"),
        }
    go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
    if source_id == "production_pilot_evidence_bundle":
        return {
            "controlled_pilot_ready": payload.get("controlled_pilot_ready"),
            "controlled_pilot": go_no_go.get("controlled_pilot"),
            "missing_condition_count": payload.get("missing_condition_count"),
            "final_verification_passed_count": payload.get("final_verification_passed_count"),
            "final_verification_requirement_count": payload.get("final_verification_requirement_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch")
            or go_no_go.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
            "auto_approved": payload.get("auto_approved"),
            "auto_closed": payload.get("auto_closed"),
        }
    if source_id == "production_landing_final_verification":
        return {
            "passed_count": payload.get("passed_count"),
            "requirement_count": payload.get("requirement_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
            "auto_approved": payload.get("auto_approved"),
            "auto_closed": payload.get("auto_closed"),
        }
    if source_id == "production_landing_signoff_closeout":
        return {
            "final_status": payload.get("final_status"),
            "target_record_written": payload.get("target_record_written"),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
            "auto_signed": payload.get("auto_signed"),
            "auto_approved": payload.get("auto_approved"),
            "auto_closed": payload.get("auto_closed"),
        }
    if source_id == "production_pilot_bootstrap":
        return {
            "evidence_count": payload.get("evidence_count"),
            "local_service_status": (payload.get("local_service_smoke") or {}).get("status")
            if isinstance(payload.get("local_service_smoke"), dict)
            else payload.get("local_service_status"),
            "signoff_closeout_passed": payload.get("signoff_closeout_passed"),
            "final_verification_passed": payload.get("final_verification_passed"),
            "pilot_evidence_bundle_passed": payload.get("pilot_evidence_bundle_passed"),
            "operations_console_smoke_status": payload.get("operations_console_smoke_status"),
            "public_production_direct_launch": (payload.get("go_no_go") or {}).get("public_production_direct_launch")
            if isinstance(payload.get("go_no_go"), dict)
            else payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    return {}


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _evaluate_gate(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing_conditions: list[str] = []
    delivery = sources.get("controlled_pilot_delivery_gate", {})
    bundle = sources["production_pilot_evidence_bundle"]
    final = sources["production_landing_final_verification"]
    closeout = sources["production_landing_signoff_closeout"]
    bootstrap = sources["production_pilot_bootstrap"]

    delivery_summary = delivery.get("summary", {}) if isinstance(delivery.get("summary"), dict) else {}
    accepted_remaining_gaps = [
        str(item)
        for item in (
            delivery_summary.get("accepted_remaining_gaps")
            if isinstance(delivery_summary.get("accepted_remaining_gaps"), list)
            else []
        )
    ]
    delivery_ready = (
        delivery.get("status") == "success"
        and delivery_summary.get("controlled_pilot_delivery_ready") is True
        and _int_value(delivery_summary.get("missing_condition_count")) == 0
        and delivery_summary.get("enterprise_landing_scope") == "controlled_internal_pilot"
    )

    bundle_summary = bundle.get("summary", {})
    evidence_ready = (
        bundle.get("status") == "success"
        and bundle_summary.get("controlled_pilot_ready") is True
        and bundle_summary.get("controlled_pilot") == "Go"
        and _int_value(bundle_summary.get("missing_condition_count")) == 0
    )
    if not delivery_ready and not evidence_ready:
        missing_conditions.append("controlled_pilot_launch_gate:evidence_bundle_not_go")

    final_summary = final.get("summary", {})
    passed_count = _int_value(final_summary.get("passed_count"))
    requirement_count = _int_value(final_summary.get("requirement_count"))
    final_ready = final.get("status") == "success" and requirement_count > 0 and passed_count == requirement_count
    if not delivery_ready and not final_ready:
        missing_conditions.append("controlled_pilot_launch_gate:final_verification_not_complete")

    closeout_summary = closeout.get("summary", {})
    signoff_ready = (
        closeout.get("status") == "success"
        and closeout_summary.get("final_status") == "success"
        and closeout_summary.get("target_record_written") is True
        and _int_value(closeout_summary.get("missing_condition_count")) == 0
    )
    if not delivery_ready and not signoff_ready:
        missing_conditions.append("controlled_pilot_launch_gate:signoff_closeout_not_complete")

    public_values = [
        delivery_summary.get("public_production_direct_launch"),
        bundle_summary.get("public_production_direct_launch"),
        final_summary.get("public_production_direct_launch"),
        closeout_summary.get("public_production_direct_launch"),
        bootstrap.get("summary", {}).get("public_production_direct_launch"),
    ]
    public_boundary_ok = all(str(value or "No-Go") == "No-Go" for value in public_values)
    if not public_boundary_ok:
        missing_conditions.append("controlled_pilot_launch_gate:public_direct_launch_boundary_changed")

    secret_plaintext_output = any(
        source.get("summary", {}).get("secret_plaintext_output") is True or source.get("secret_detected") is True
        for source in sources.values()
    )
    if secret_plaintext_output:
        missing_conditions.append("controlled_pilot_launch_gate:secret_plaintext_output_detected")

    auto_approval_blocked = any(
        source.get("summary", {}).get(flag) is True
        for source in (delivery, bundle, final, closeout)
        for flag in ("auto_signed", "auto_approved", "auto_closed")
    )
    if auto_approval_blocked:
        missing_conditions.append("controlled_pilot_launch_gate:auto_approval_or_close_detected")

    ready = len(missing_conditions) == 0
    return {
        "status": "ready" if ready else "blocked",
        "ready_for_controlled_pilot": ready,
        "controlled_pilot": "Go" if ready else "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
        "delivery_gate_status": str(delivery.get("status") or "skipped"),
        "accepted_remaining_gaps": accepted_remaining_gaps,
        "evidence_bundle_status": str(bundle.get("status") or "skipped"),
        "final_verification_status": str(final.get("status") or "skipped"),
        "signoff_closeout_status": str(closeout.get("status") or "skipped"),
        "bootstrap_status": str(bootstrap.get("status") or "skipped"),
        "final_verification_passed_count": passed_count,
        "final_verification_requirement_count": requirement_count,
        "missing_conditions": missing_conditions,
        "missing_condition_count": len(missing_conditions),
        "safe_next_action": "start_controlled_internal_pilot_window" if ready else "resolve_missing_conditions_before_pilot",
        "operator_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\production_landing_signoff_closeout.ps1",
        "secret_plaintext_output": secret_plaintext_output,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Controlled Pilot Launch Gate",
        "",
        f"- status: {payload['status']}",
        f"- ready_for_controlled_pilot: {payload['ready_for_controlled_pilot']}",
        f"- controlled_pilot: {payload['controlled_pilot']}",
        f"- public_production_direct_launch: {payload['public_production_direct_launch']}",
        f"- manual_signoff_required: {payload['manual_signoff_required']}",
        f"- missing_condition_count: {payload['missing_condition_count']}",
        f"- safe_next_action: {payload['safe_next_action']}",
        f"- secret_plaintext_output: {payload['secret_plaintext_output']}",
        "",
        "## Sources",
    ]
    for source_id, source in payload["sources"].items():
        lines.append(f"- {source_id}: status={source['status']} present={source['present']}")
    lines.extend(["", "## Missing Conditions"])
    if payload["missing_conditions"]:
        lines.extend(f"- {item}" for item in payload["missing_conditions"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_controlled_pilot_launch_gate(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"])
    sources = {source_id: _read_latest_source(source_id, directory) for source_id, directory in SOURCE_DIRS.items()}
    gate = _evaluate_gate(sources)
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.11",
        "phase": "v4.8 Controlled Pilot Launch Gate",
        "mode": "read_only_derived_gate",
        "read_only": True,
        "status_vocabulary": STATUS_VOCABULARY,
        "sources": sources,
        **gate,
    }

    destination = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    if not destination.is_absolute():
        destination = ROOT_DIR / destination
    destination.mkdir(parents=True, exist_ok=True)
    short_commit = (commit[:8] if commit else "no_commit")
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_launch_gate"
    json_path = destination / f"{stem}.json"
    markdown_path = destination / f"{stem}.md"
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(markdown_path)
    payload["output_dir"] = str(destination)

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(payload, markdown_path)
    return {
        "status": payload["status"],
        "generated_at": payload["generated_at"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "ready_for_controlled_pilot": payload["ready_for_controlled_pilot"],
        "controlled_pilot": payload["controlled_pilot"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only controlled pilot launch gate report.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    summary = build_controlled_pilot_launch_gate(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
