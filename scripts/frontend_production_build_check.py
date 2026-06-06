from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "frontend_production_build"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
BUILD_COMMAND = ["npm.cmd" if os.name == "nt" else "npm", "run", "build"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(text: str) -> bool:
    lowered = (text or "").lower()
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
            "redis://",
        )
    )


def _safe_tail(text: str, max_lines: int = 80) -> list[str]:
    safe: list[str] = []
    for line in (text or "").splitlines()[-max_lines:]:
        safe.append("[redacted-secret-like-build-line]" if _contains_secret_like(line) else line)
    return safe


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 前端生产构建检查报告",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execute: {payload.get('execute', False)}",
        f"- build_command: {payload.get('build_command', '')}",
        f"- frontend_dir_present: {payload.get('frontend_dir_present', False)}",
        f"- package_json_present: {payload.get('package_json_present', False)}",
        f"- build_executed: {payload.get('build_executed', False)}",
        f"- secret_plaintext_output: {payload.get('secret_plaintext_output', False)}",
        "",
        "## 边界",
        "- 默认不执行构建；必须显式传入 --execute。",
        "- 仅执行 frontend 生产构建，不启动服务，不连接后端或外部 API。",
        "- 根据运行平台选择 npm.cmd 或 npm，避免 Windows PowerShell npm.ps1 执行策略拦截，同时兼容 Linux CI。",
        "- 构建输出只保留脱敏摘要，不输出 secret 原文。",
        "",
    ]
    return "\n".join(lines)


def _write_report(payload: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    short_commit = str(payload.get("commit") or "unknown")[:8]
    stem = f"{payload['generated_at'].replace(':', '-').replace('+', '_')}_{short_commit}_frontend_production_build"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(md_path)}

def build_frontend_production_build_check(
    *,
    output_dir: str | Path | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    if _contains_secret_like(commit):
        commit = "redacted"
    frontend_present = FRONTEND_DIR.exists() and FRONTEND_DIR.is_dir()
    package_json_present = (FRONTEND_DIR / "package.json").exists()
    package_lock_present = (FRONTEND_DIR / "package-lock.json").exists()
    node_modules_present = (FRONTEND_DIR / "node_modules").exists()
    missing_conditions: list[str] = []
    build_output_tail: list[str] = []
    build_error_tail: list[str] = []
    return_code: int | None = None

    if not execute:
        missing_conditions.append("cli:--execute_not_requested")
        status = "skipped"
    elif not frontend_present:
        missing_conditions.append("local:frontend_dir_missing")
        status = "blocked"
    elif not package_json_present:
        missing_conditions.append("local:frontend_package_json_missing")
        status = "blocked"
    elif not package_lock_present:
        missing_conditions.append("local:frontend_package_lock_missing")
        status = "blocked"
    else:
        completed = subprocess.run(
            BUILD_COMMAND,
            cwd=str(FRONTEND_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=120,
        )
        return_code = completed.returncode
        build_output_tail = _safe_tail(completed.stdout)
        build_error_tail = _safe_tail(completed.stderr)
        status = "success" if completed.returncode == 0 else "failed"

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.4",
        "phase": "v4.5 Phase 25.6 Frontend Production Build Check",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "execute": execute,
        "frontend_dir_present": frontend_present,
        "package_json_present": package_json_present,
        "package_lock_present": package_lock_present,
        "node_modules_present": node_modules_present,
        "build_command": " ".join(BUILD_COMMAND),
        "build_executed": bool(execute and not missing_conditions),
        "return_code": return_code,
        "missing_conditions": missing_conditions,
        "stdout_tail": build_output_tail,
        "stderr_tail": build_error_tail,
        "secret_plaintext_output": False,
        "go_no_go": {
            "frontend_production_build": "Manual-Review" if status == "success" else "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "output_dir": str(output_root),
    }
    payload_for_secret_scan = dict(payload)
    payload_for_secret_scan["stdout_tail"] = []
    payload_for_secret_scan["stderr_tail"] = []
    if _contains_secret_like(json.dumps(payload_for_secret_scan, ensure_ascii=False)):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    paths = _write_report(payload, output_root)
    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "execute": execute,
        "build_executed": payload["build_executed"],
        "return_code": return_code,
        "frontend_dir_present": frontend_present,
        "package_json_present": package_json_present,
        "package_lock_present": package_lock_present,
        "node_modules_present": node_modules_present,
        "missing_conditions": missing_conditions,
        "secret_plaintext_output": False,
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
        "output_dir": str(output_root),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成前端生产构建检查报告。默认不执行构建。")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true", help="执行前端生产构建命令。")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_frontend_production_build_check(output_dir=args.output_dir, execute=args.execute)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "skipped", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
