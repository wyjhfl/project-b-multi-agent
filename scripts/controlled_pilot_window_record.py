from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_window_record"
LAUNCH_PACKAGE_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_launch_package"


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


def _load_launch_package(package_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(package_path) if package_path else _latest_json(LAUNCH_PACKAGE_DIR)
    if path is None:
        return {
            "present": False,
            "status": "skipped",
            "path": "",
            "payload": {},
            "missing_conditions": ["controlled_pilot_launch_package:latest_report_missing"],
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
            "missing_conditions": ["controlled_pilot_launch_package:latest_report_missing"],
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
            "missing_conditions": ["controlled_pilot_launch_package:json_parse_failed"],
            "secret_detected": False,
        }
    secret_detected = _contains_secret_like(payload)
    return {
        "present": True,
        "status": "blocked" if secret_detected else str(payload.get("status") or "skipped"),
        "path": _safe_text(path),
        "payload": payload,
        "missing_conditions": ["controlled_pilot_launch_package:secret_like_text_detected"] if secret_detected else [],
        "secret_detected": secret_detected,
    }


def _derive_window_status(*, package: dict[str, Any], confirm_open: str) -> tuple[str, list[str]]:
    missing = list(package.get("missing_conditions", []))
    payload = package.get("payload") if isinstance(package.get("payload"), dict) else {}
    package_ready = (
        package.get("present") is True
        and package.get("status") == "ready"
        and payload.get("launch_package_ready") is True
        and payload.get("controlled_pilot") == "Go"
        and payload.get("public_production_direct_launch") == "No-Go"
        and int(payload.get("missing_condition_count") or 0) == 0
        and payload.get("secret_plaintext_output") is False
    )
    if not package_ready:
        missing.append("controlled_pilot_window_record:launch_package_not_ready")
    if confirm_open != "YES":
        missing.append("controlled_pilot_window_record:confirm_open_not_yes")
    if package.get("secret_detected") is True:
        missing.append("controlled_pilot_window_record:secret_like_text_detected")
    if any(item.endswith("secret_like_text_detected") for item in missing):
        return "blocked", sorted(set(missing))
    if not package_ready:
        return "blocked", sorted(set(missing))
    if confirm_open != "YES":
        return "skipped", sorted(set(missing))
    return "opened", []


def _package_summary(package: dict[str, Any]) -> dict[str, Any]:
    payload = package.get("payload") if isinstance(package.get("payload"), dict) else {}
    return {
        "present": bool(package.get("present", False)),
        "status": str(package.get("status") or "skipped"),
        "path": _safe_text(package.get("path") or ""),
        "launch_package_ready": bool(payload.get("launch_package_ready", False)),
        "controlled_pilot": _safe_text(payload.get("controlled_pilot") or "Manual-Review"),
        "public_production_direct_launch": _safe_text(payload.get("public_production_direct_launch") or "No-Go"),
        "missing_condition_count": int(payload.get("missing_condition_count") or 0),
        "safe_next_action": _safe_text(payload.get("safe_next_action") or ""),
        "operator_command_count": len(payload.get("operator_commands", []) if isinstance(payload.get("operator_commands"), list) else []),
        "pilot_role_count": len(payload.get("pilot_roles", []) if isinstance(payload.get("pilot_roles"), list) else []),
        "source_count": len(payload.get("sources", {}) if isinstance(payload.get("sources"), dict) else {}),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Controlled Pilot Window Record",
        "",
        f"- status: {payload['status']}",
        f"- window_id: {payload['window_id']}",
        f"- opened: {payload['opened']}",
        f"- controlled_pilot: {payload['controlled_pilot']}",
        f"- public_production_direct_launch: {payload['public_production_direct_launch']}",
        f"- confirm_open: {payload['confirm_open']}",
        f"- missing_condition_count: {payload['missing_condition_count']}",
        f"- secret_plaintext_output: {payload['secret_plaintext_output']}",
        "",
        "## Missing Conditions",
    ]
    lines.extend([f"- {item}" for item in payload["missing_conditions"]] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_controlled_pilot_window_record(
    *,
    output_dir: str | Path | None = None,
    launch_package_path: str | Path | None = None,
    window_id: str = "",
    opened_by: str = "",
    confirm_open: str = "",
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"])
    package = _load_launch_package(launch_package_path)
    status, missing = _derive_window_status(package=package, confirm_open=confirm_open)
    package_summary = _package_summary(package)
    safe_window_id = _safe_text(window_id or f"controlled-pilot-{generated_at[:10]}")
    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.13",
        "phase": "v4.8 Controlled Pilot Window Record",
        "mode": "manual_window_record",
        "read_only": True,
        "status": status,
        "window_id": safe_window_id,
        "opened": status == "opened",
        "opened_by": _safe_text(opened_by),
        "confirm_open": "YES" if confirm_open == "YES" else "not_confirmed",
        "controlled_pilot": "Go" if status == "opened" else package_summary["controlled_pilot"],
        "public_production_direct_launch": "No-Go",
        "manual_signoff_required": True,
        "launch_package": package_summary,
        "missing_conditions": missing,
        "missing_condition_count": len(missing),
        "rollback_required": True,
        "external_expansion_requires_new_manual_go_no_go": True,
        "secret_plaintext_output": bool(package_summary.get("secret_plaintext_output", False) or package.get("secret_detected")),
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
    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_window_record"
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
        "window_id": payload["window_id"],
        "opened": payload["opened"],
        "missing_condition_count": payload["missing_condition_count"],
        "secret_plaintext_output": payload["secret_plaintext_output"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a controlled pilot window record.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--launch-package", default=None)
    parser.add_argument("--window-id", default="")
    parser.add_argument("--opened-by", default="")
    parser.add_argument("--confirm-open", default="")
    args = parser.parse_args()
    summary = build_controlled_pilot_window_record(
        output_dir=args.output_dir,
        launch_package_path=args.launch_package,
        window_id=args.window_id,
        opened_by=args.opened_by,
        confirm_open=args.confirm_open,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
