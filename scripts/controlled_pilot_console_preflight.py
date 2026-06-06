from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_console_preflight"
VERIFY_REPORT_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_console_verify"
CONSOLE_RUNTIME_DIR = ROOT_DIR / "docs" / "reports" / "controlled_pilot_console"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _port_is_listening(host: str, port: int, timeout_seconds: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(path: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        return str(payload.get("generated_at") or ""), path.stat().st_mtime, path.name

    return max(files, key=sort_key)


def _latest_verify_summary() -> dict[str, Any]:
    latest = _latest_json(VERIFY_REPORT_DIR, "*_controlled_pilot_console_verify.json")
    if latest is None:
        return {
            "latest_report_present": False,
            "latest_json_path": "",
            "status": "skipped",
            "controlled_internal_pilot": "Manual-Review",
            "public_production_direct_launch": "No-Go",
            "missing_condition_count": 0,
            "secret_plaintext_output": False,
        }
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {
            "latest_report_present": True,
            "latest_json_path": str(latest),
            "status": "blocked",
            "controlled_internal_pilot": "No-Go",
            "public_production_direct_launch": "No-Go",
            "missing_condition_count": 1,
            "secret_plaintext_output": False,
        }
    return {
        "latest_report_present": True,
        "latest_json_path": str(latest),
        "status": str(payload.get("status") or "skipped"),
        "controlled_internal_pilot": str(payload.get("controlled_internal_pilot") or "Manual-Review"),
        "public_production_direct_launch": str(payload.get("public_production_direct_launch") or "No-Go"),
        "missing_condition_count": int(payload.get("missing_condition_count") or 0),
        "secret_plaintext_output": bool(payload.get("secret_plaintext_output", False)),
    }


def build_controlled_pilot_console_preflight(
    *,
    output_dir: str | Path | None = None,
    backend_port: int = 8000,
    frontend_port: int = 3003,
    write_report: bool = True,
) -> dict[str, Any]:
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    checks = {
        "python_wrapper_present": (ROOT_DIR / "scripts" / "codex_python.ps1").exists(),
        "console_up_script_present": (ROOT_DIR / "scripts" / "controlled_pilot_console_up.ps1").exists(),
        "console_down_script_present": (ROOT_DIR / "scripts" / "controlled_pilot_console_down.ps1").exists(),
        "console_verify_script_present": (ROOT_DIR / "scripts" / "controlled_pilot_console_verify.ps1").exists(),
        "frontend_dir_present": FRONTEND_DIR.exists(),
        "frontend_package_json_present": (FRONTEND_DIR / "package.json").exists(),
        "frontend_node_modules_present": (FRONTEND_DIR / "node_modules").exists(),
        "next_cli_present": (FRONTEND_DIR / "node_modules" / "next" / "dist" / "bin" / "next").exists(),
        "next_build_id_present": (FRONTEND_DIR / ".next" / "BUILD_ID").exists(),
        "node_on_path": shutil.which("node.exe") is not None or shutil.which("node") is not None,
        "npm_on_path": shutil.which("npm.cmd") is not None or shutil.which("npm") is not None,
        "backend_port_listening": _port_is_listening("127.0.0.1", backend_port),
        "frontend_port_listening": _port_is_listening("127.0.0.1", frontend_port),
        "pid_file_present": (CONSOLE_RUNTIME_DIR / "controlled_pilot_console_processes.json").exists(),
    }
    latest_verify = _latest_verify_summary()
    blocking_conditions: list[str] = []
    required_true = [
        "python_wrapper_present",
        "console_up_script_present",
        "console_down_script_present",
        "console_verify_script_present",
        "frontend_dir_present",
        "frontend_package_json_present",
        "frontend_node_modules_present",
        "next_cli_present",
        "next_build_id_present",
        "node_on_path",
        "npm_on_path",
    ]
    for key in required_true:
        if checks[key] is not True:
            blocking_conditions.append(f"{key}:missing_or_false")
    if checks["backend_port_listening"]:
        blocking_conditions.append(f"backend_port:{backend_port}:already_listening")
    if checks["frontend_port_listening"]:
        blocking_conditions.append(f"frontend_port:{frontend_port}:already_listening")
    if checks["pid_file_present"]:
        blocking_conditions.append("controlled_pilot_console:pid_file_present")
    if latest_verify["secret_plaintext_output"]:
        blocking_conditions.append("latest_verify:secret_plaintext_output")
    if latest_verify["public_production_direct_launch"] != "No-Go":
        blocking_conditions.append("latest_verify:public_direct_launch_not_no_go")

    ready = not blocking_conditions
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.8.20",
        "phase": "v4.8 Controlled Pilot Console Preflight",
        "status_vocabulary": STATUS_VOCABULARY,
        "mode": "read_only_local_console_preflight",
        "status": "ready" if ready else "blocked",
        "ready_for_local_verify": ready,
        "recommended_command": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\controlled_pilot_console_verify.ps1",
        "backend_url": f"http://127.0.0.1:{backend_port}",
        "frontend_url": f"http://127.0.0.1:{frontend_port}/operations",
        "checks": checks,
        "latest_verify": latest_verify,
        "blocking_conditions": sorted(set(blocking_conditions)),
        "blocking_condition_count": len(set(blocking_conditions)),
        "public_production_direct_launch": "No-Go",
        "real_llm_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
    }

    if write_report:
        output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        output_root.mkdir(parents=True, exist_ok=True)
        short_commit = commit[:8] if commit != "unknown" else "unknown"
        stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_controlled_pilot_console_preflight"
        json_path = output_root / f"{stem}.json"
        markdown_path = output_root / f"{stem}.md"
        payload["json_path"] = str(json_path)
        payload["markdown_path"] = str(markdown_path)
        payload["output_dir"] = str(output_root)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(_build_markdown(payload), encoding="utf-8")
    return payload


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 受控试点控制台本地预检报告",
        "",
        f"- status: {payload.get('status', '')}",
        f"- ready_for_local_verify: {payload.get('ready_for_local_verify', False)}",
        f"- recommended_command: `{payload.get('recommended_command', '')}`",
        f"- public_production_direct_launch: {payload.get('public_production_direct_launch', 'No-Go')}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 阻断条件",
    ]
    blocking = payload.get("blocking_conditions", [])
    lines.extend(f"- {item}" for item in blocking) if blocking else lines.append("- none")
    lines.extend(["", "## 检查项"])
    for key, value in payload.get("checks", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build controlled pilot console local preflight report.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=3003)
    parser.add_argument("--no-write-report", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_controlled_pilot_console_preflight(
        output_dir=args.output_dir,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        write_report=not args.no_write_report,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status={report['status']}")
        print(f"ready_for_local_verify={report['ready_for_local_verify']}")
        print(f"blocking_condition_count={report['blocking_condition_count']}")
        print(f"public_production_direct_launch={report['public_production_direct_launch']}")
        print(f"secret_plaintext_output={report['secret_plaintext_output']}")
        if report.get("json_path"):
            print(f"json_path={report['json_path']}")
            print(f"markdown_path={report['markdown_path']}")
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
