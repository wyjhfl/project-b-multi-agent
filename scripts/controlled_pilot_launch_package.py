from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_package"

SOURCE_DIRS = {
    "controlled_pilot_launch_gate": ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_gate",
    "production_landing_signoff_closeout": ROOT_DIR / "docs" / "reports" / "production_landing_signoff_closeout",
    "production_landing_final_verification": ROOT_DIR / "docs" / "reports" / "production_landing_final_verification",
    "production_pilot_evidence_bundle": ROOT_DIR / "docs" / "reports" / "production_pilot_evidence_bundle",
    "production_pilot_bootstrap": ROOT_DIR / "docs" / "reports" / "production_pilot_bootstrap",
    "operations_console_landing_smoke": ROOT_DIR / "docs" / "reports" / "operations_console_landing_smoke",
}

REQUIRED_SOURCES = (
    "controlled_pilot_launch_gate",
    "production_landing_signoff_closeout",
    "production_landing_final_verification",
    "production_pilot_evidence_bundle",
)


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
    if any(marker in lowered for marker in ("sk-", "tp-", "bearer ", "postgresql://", "postgres://", "redis://")):
        return True
    for marker in ("api_key=", "apikey=", "token=", "password=", "client_secret=", "jwt_secret="):
        if marker in lowered:
            return True
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


def _source_summary(source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if source_id == "controlled_pilot_launch_gate":
        return {
            "ready_for_controlled_pilot": payload.get("ready_for_controlled_pilot"),
            "controlled_pilot": payload.get("controlled_pilot"),
            "missing_condition_count": payload.get("missing_condition_count"),
            "safe_next_action": payload.get("safe_next_action"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "manual_signoff_required": payload.get("manual_signoff_required"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "production_landing_signoff_closeout":
        return {
            "final_status": payload.get("final_status"),
            "target_record_written": payload.get("target_record_written"),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "production_landing_final_verification":
        return {
            "passed_count": payload.get("passed_count"),
            "requirement_count": payload.get("requirement_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "production_pilot_evidence_bundle":
        go_no_go = payload.get("go_no_go") if isinstance(payload.get("go_no_go"), dict) else {}
        return {
            "controlled_pilot_ready": payload.get("controlled_pilot_ready"),
            "controlled_pilot": go_no_go.get("controlled_pilot"),
            "missing_condition_count": payload.get("missing_condition_count"),
            "public_production_direct_launch": payload.get("public_production_direct_launch")
            or go_no_go.get("public_production_direct_launch"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "production_pilot_bootstrap":
        return {
            "evidence_count": payload.get("evidence_count"),
            "signoff_closeout_passed": payload.get("signoff_closeout_passed"),
            "final_verification_passed": payload.get("final_verification_passed"),
            "pilot_evidence_bundle_passed": payload.get("pilot_evidence_bundle_passed"),
            "operations_console_smoke_status": payload.get("operations_console_smoke_status"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    if source_id == "operations_console_landing_smoke":
        return {
            "status": payload.get("status"),
            "execute": payload.get("execute"),
            "page_http_status": payload.get("page_http_status"),
            "summary_http_status": payload.get("summary_http_status"),
            "secret_plaintext_output": payload.get("secret_plaintext_output"),
        }
    return {}


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
            "missing_conditions": [f"{source_id}:latest_report_missing"] if source_id in REQUIRED_SOURCES else [],
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
    secret_detected = _contains_secret_like(payload)
    return {
        "source_id": source_id,
        "present": True,
        "status": "blocked" if secret_detected else str(payload.get("status") or "skipped"),
        "latest_json_path": _safe_text(latest),
        "generated_at": _safe_text(payload.get("generated_at") or ""),
        "summary": _source_summary(source_id, payload),
        "missing_conditions": [_safe_text(item) for item in missing[:16]],
        "secret_detected": secret_detected,
    }


def _derive_package(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing_conditions: list[str] = []
    for source_id in REQUIRED_SOURCES:
        source = sources[source_id]
        if source.get("present") is not True:
            missing_conditions.append(f"{source_id}:latest_report_missing")
        if source.get("secret_detected") is True:
            missing_conditions.append(f"{source_id}:secret_like_text_detected")

    gate = sources["controlled_pilot_launch_gate"]
    gate_summary = gate.get("summary", {})
    gate_ready = (
        gate.get("status") == "ready"
        and gate_summary.get("ready_for_controlled_pilot") is True
        and gate_summary.get("controlled_pilot") == "Go"
        and int(gate_summary.get("missing_condition_count") or 0) == 0
    )
    if not gate_ready:
        missing_conditions.append("controlled_pilot_launch_package:launch_gate_not_ready")

    public_values = [source.get("summary", {}).get("public_production_direct_launch") for source in sources.values()]
    if not all(str(value or "No-Go") == "No-Go" for value in public_values):
        missing_conditions.append("controlled_pilot_launch_package:public_direct_launch_boundary_changed")

    secret_plaintext_output = any(
        source.get("secret_detected") is True or source.get("summary", {}).get("secret_plaintext_output") is True
        for source in sources.values()
    )
    if secret_plaintext_output:
        missing_conditions.append("controlled_pilot_launch_package:secret_plaintext_output_detected")

    ready = len(set(missing_conditions)) == 0
    return {
        "status": "ready" if ready else "blocked",
        "launch_package_ready": ready,
        "controlled_pilot": "Go" if ready else "Manual-Review",
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
        "missing_conditions": sorted(set(missing_conditions)),
        "missing_condition_count": len(set(missing_conditions)),
        "safe_next_action": "open_controlled_pilot_window" if ready else "resolve_launch_package_missing_conditions",
        "operator_commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\production_landing_signoff_closeout.ps1",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 scripts\\controlled_pilot_launch_gate.py",
            "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 scripts\\controlled_pilot_launch_package.py",
        ],
        "pilot_roles": [
            {"role": "release_manager", "responsibility": "confirm launch window and rollback authority"},
            {"role": "security_reviewer", "responsibility": "confirm secret redaction and access boundary"},
            {"role": "business_owner", "responsibility": "confirm pilot business scope"},
            {"role": "operations_owner", "responsibility": "monitor service health and evidence capture"},
        ],
        "launch_window": {
            "scope": "controlled_internal_pilot",
            "public_production_direct_launch": "No-Go",
            "rollback_required": True,
            "external_expansion_requires_new_manual_go_no_go": True,
        },
        "secret_plaintext_output": secret_plaintext_output,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Controlled Pilot Launch Package",
        "",
        f"- status: {payload['status']}",
        f"- launch_package_ready: {payload['launch_package_ready']}",
        f"- controlled_pilot: {payload['controlled_pilot']}",
        f"- public_production_direct_launch: {payload['public_production_direct_launch']}",
        f"- missing_condition_count: {payload['missing_condition_count']}",
        f"- safe_next_action: {payload['safe_next_action']}",
        "",
        "## Operator Commands",
        *[f"- {item}" for item in payload["operator_commands"]],
        "",
        "## Sources",
    ]
    lines.extend(f"- {source_id}: status={source['status']} present={source['present']}" for source_id, source in payload["sources"].items())
    lines.extend(["", "## Missing Conditions"])
    lines.extend([f"- {item}" for item in payload["missing_conditions"]] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_controlled_pilot_launch_package(
    *,
    output_dir: str | Path | None = None,
    source_dirs: dict[str, str | Path] | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"])
    effective_dirs = {key: Path(value) for key, value in (source_dirs or SOURCE_DIRS).items()}
    sources = {source_id: _read_latest_source(source_id, directory) for source_id, directory in effective_dirs.items()}
    package = _derive_package(sources)
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.12",
        "phase": "v4.8 Controlled Pilot Launch Package",
        "mode": "read_only_launch_package",
        "read_only": True,
        "sources": sources,
        **package,
    }

    destination = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not destination.is_absolute():
        destination = ROOT_DIR / destination
    destination.mkdir(parents=True, exist_ok=True)
    short_commit = commit[:8] if commit else "no_commit"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_launch_package"
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
        "launch_package_ready": payload["launch_package_ready"],
        "controlled_pilot": payload["controlled_pilot"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only controlled pilot launch package report.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    summary = build_controlled_pilot_launch_package(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
