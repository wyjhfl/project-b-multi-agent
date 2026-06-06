from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
root_path = str(ROOT_DIR)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from fastapi.testclient import TestClient

from app.main import app

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_window_status"
WINDOW_RECORD_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_window_record"


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
    return any(
        marker in lowered
        for marker in (
            "sk-",
            "tp-",
            "bearer ",
            "api_key=",
            "apikey=",
            "token=",
            "password=",
            "client_secret=",
            "jwt_secret=",
            "postgresql://",
            "postgres://",
            "redis://",
        )
    )


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


def _load_window_record(window_record_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(window_record_path) if window_record_path else _latest_json(WINDOW_RECORD_DIR)
    if path is None:
        return {
            "present": False,
            "status": "skipped",
            "path": "",
            "payload": {},
            "missing_conditions": ["controlled_pilot_window_record:latest_report_missing"],
            "secret_detected": False,
        }
    if not path.is_absolute():
        path = ROOT_DIR / path
    if not path.exists() or not path.is_file():
        return {
            "present": False,
            "status": "skipped",
            "path": _safe_text(path),
            "payload": {},
            "missing_conditions": ["controlled_pilot_window_record:latest_report_missing"],
            "secret_detected": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "present": True,
            "status": "blocked",
            "path": _safe_text(path),
            "payload": {},
            "missing_conditions": ["controlled_pilot_window_record:json_parse_failed"],
            "secret_detected": False,
        }
    secret_detected = _contains_secret_like(payload)
    return {
        "present": True,
        "status": "blocked" if secret_detected else str(payload.get("status") or "skipped"),
        "path": _safe_text(path),
        "payload": payload,
        "missing_conditions": ["controlled_pilot_window_record:secret_like_text_detected"] if secret_detected else [],
        "secret_detected": secret_detected,
    }


def _collect_operations_summary() -> dict[str, Any]:
    try:
        with TestClient(app) as client:
            response = client.get("/operations/summary")
        if response.status_code != 200:
            return {
                "status": "failed",
                "http_status": response.status_code,
                "missing_conditions": ["operations_summary:http_status_not_200"],
            }
        payload = response.json()
    except Exception as exc:
        return {
            "status": "failed",
            "http_status": None,
            "missing_conditions": [f"operations_summary:unavailable:{exc.__class__.__name__}"],
        }

    health = payload.get("health") if isinstance(payload.get("health"), dict) else {}
    deployment = payload.get("deployment") if isinstance(payload.get("deployment"), dict) else {}
    observability = payload.get("observability") if isinstance(payload.get("observability"), dict) else {}
    window_record = observability.get("controlled_pilot_window_record")
    launch_package = observability.get("controlled_pilot_launch_package")
    gate = observability.get("controlled_pilot_launch_gate")

    missing_conditions: list[str] = []
    if str(health.get("status") or "") != "ok":
        missing_conditions.append("operations_summary:health_not_ok")
    if str((window_record or {}).get("public_production_direct_launch") or "No-Go") != "No-Go":
        missing_conditions.append("operations_summary:window_public_launch_not_no_go")
    if bool((window_record or {}).get("secret_plaintext_output", False)):
        missing_conditions.append("operations_summary:window_secret_plaintext_output")
    if bool((launch_package or {}).get("secret_plaintext_output", False)):
        missing_conditions.append("operations_summary:package_secret_plaintext_output")
    if bool((gate or {}).get("secret_plaintext_output", False)):
        missing_conditions.append("operations_summary:gate_secret_plaintext_output")

    return {
        "status": "success" if not missing_conditions else "blocked",
        "http_status": 200,
        "missing_conditions": missing_conditions,
        "health_status": str(health.get("status") or ""),
        "deployment_ok": bool(deployment.get("ok", False)),
        "deployment_error_count": int(deployment.get("error_count", 0) or 0),
        "deployment_warning_count": int(deployment.get("warning_count", 0) or 0),
        "controlled_pilot_window_status": str((window_record or {}).get("status") or "skipped"),
        "controlled_pilot_window_opened": bool((window_record or {}).get("opened", False)),
        "controlled_pilot_window_id": _safe_text((window_record or {}).get("window_id") or ""),
        "launch_package_status": str((launch_package or {}).get("status") or "skipped"),
        "launch_package_ready": bool((launch_package or {}).get("launch_package_ready", False)),
        "launch_gate_status": str((gate or {}).get("status") or "skipped"),
        "launch_gate_ready": bool((gate or {}).get("ready_for_controlled_pilot", False)),
        "public_production_direct_launch": "No-Go",
    }


def _window_summary(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    launch_package = payload.get("launch_package") if isinstance(payload.get("launch_package"), dict) else {}
    return {
        "present": bool(record.get("present", False)),
        "status": str(record.get("status") or "skipped"),
        "path": _safe_text(record.get("path") or ""),
        "opened": bool(payload.get("opened", False)),
        "window_id": _safe_text(payload.get("window_id") or ""),
        "opened_by": _safe_text(payload.get("opened_by") or ""),
        "controlled_pilot": _safe_text(payload.get("controlled_pilot") or "Manual-Review"),
        "public_production_direct_launch": _safe_text(payload.get("public_production_direct_launch") or "No-Go"),
        "missing_condition_count": int(payload.get("missing_condition_count") or 0),
        "rollback_required": bool(payload.get("rollback_required", True)),
        "launch_package_ready": bool(launch_package.get("launch_package_ready", False)),
        "launch_package_status": _safe_text(launch_package.get("status") or "skipped"),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _derive_status(window: dict[str, Any], operations: dict[str, Any]) -> tuple[str, list[str]]:
    missing = [*window.get("missing_conditions", []), *operations.get("missing_conditions", [])]
    summary = _window_summary(window)
    if window.get("secret_detected") is True:
        missing.append("controlled_pilot_window_status:secret_like_text_detected")
    if window.get("present") is not True:
        missing.append("controlled_pilot_window_status:window_record_missing")
    if summary["opened"] is not True:
        missing.append("controlled_pilot_window_status:window_not_opened")
    if summary["public_production_direct_launch"] != "No-Go":
        missing.append("controlled_pilot_window_status:public_direct_launch_boundary_changed")
    if operations.get("status") == "failed":
        missing.append("controlled_pilot_window_status:operations_summary_unavailable")
    if any("secret" in item for item in missing):
        return "blocked", sorted(set(missing))
    if window.get("present") is not True:
        return "skipped", sorted(set(missing))
    if missing:
        return "degraded", sorted(set(missing))
    return "healthy", []


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Controlled Pilot Window Status Snapshot",
        "",
        f"- status: {payload['status']}",
        f"- window_id: {payload['window']['window_id']}",
        f"- opened: {payload['window']['opened']}",
        f"- operations_health: {payload['operations_summary']['health_status']}",
        f"- deployment_ok: {payload['operations_summary']['deployment_ok']}",
        f"- public_production_direct_launch: {payload['public_production_direct_launch']}",
        f"- missing_condition_count: {payload['missing_condition_count']}",
        "",
        "## Missing Conditions",
    ]
    lines.extend([f"- {item}" for item in payload["missing_conditions"]] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_controlled_pilot_window_status_snapshot(
    *,
    output_dir: str | Path | None = None,
    window_record_path: str | Path | None = None,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"])
    window_record = _load_window_record(window_record_path)
    operations = _collect_operations_summary()
    status, missing = _derive_status(window_record, operations)
    window = _window_summary(window_record)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.14",
        "phase": "v4.8 Controlled Pilot Window Status Snapshot",
        "mode": "in_process_status_snapshot",
        "read_only": True,
        "status": status,
        "window": window,
        "operations_summary": operations,
        "missing_conditions": missing,
        "missing_condition_count": len(missing),
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": bool(window.get("secret_plaintext_output", False) or window_record.get("secret_detected")),
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "auto_approved": False,
        "auto_closed": False,
    }

    destination = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if not destination.is_absolute():
        destination = ROOT_DIR / destination
    destination.mkdir(parents=True, exist_ok=True)
    short_commit = commit[:8] if commit else "no_commit"
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_window_status"
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
        "window_id": payload["window"]["window_id"],
        "opened": payload["window"]["opened"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a controlled pilot window status snapshot.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--window-record", default=None)
    args = parser.parse_args()
    summary = build_controlled_pilot_window_status_snapshot(
        output_dir=args.output_dir,
        window_record_path=args.window_record,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
