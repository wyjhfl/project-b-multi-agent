from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import create_engine, inspect, text

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "production_migration_drill"
STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
EXPECTED_TABLES = [
    "users",
    "task_runs",
    "approval_requests",
    "audit_events",
    "runtime_task_metrics",
    "runtime_tool_metrics",
    "runtime_token_usage",
    "graph_run_states",
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

BOUNDARY_DECLARATIONS = [
    "受控 PostgreSQL migration 演练入口。",
    "默认 dry-run，不执行 Alembic migration。",
    "只有 --execute 与 PRODUCTION_MIGRATION_DRILL_ENABLED=true 同时满足，且 STORAGE_BACKEND=postgres、DATABASE_URL 非空时，才执行 alembic upgrade head。",
    "不读取或输出 DATABASE_URL、REDIS_URL、API key、token 或 password 原文。",
    "本脚本只写 Alembic schema 元数据和迁移表结构，不写业务、审计或指标样例数据。",
    "执行结果只能作为 staging/生产试点证据，不能自动宣称公网生产可直接上线。",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_present(key: str) -> bool:
    return bool(str(os.getenv(key, "") or "").strip())


def _contains_secret_like_text(value: Any) -> bool:
    if isinstance(value, str):
        text_value = value
    else:
        try:
            text_value = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text_value = str(value)
    return any(pattern.search(text_value) for pattern in SECRET_TEXT_PATTERNS)


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like_text(value) else value
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    return value


def _run_alembic_upgrade(command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None) -> dict[str, Any]:
    runner = command_runner or (
        lambda command: subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=60,
        )
    )
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    result = runner(command)
    return {
        "returncode": int(result.returncode),
        "stdout_tail": (result.stdout or "")[-2000:],
        "stderr_tail": (result.stderr or "")[-2000:],
    }


def _inspect_database() -> dict[str, Any]:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        return {"inspected": False, "error_type": "database_url_missing"}
    try:
        engine = create_engine(database_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            current_revision = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
        inspector = inspect(engine)
        tables = sorted(inspector.get_table_names())
        expected_present = {table: table in tables for table in EXPECTED_TABLES}
        return {
            "inspected": True,
            "current_revision": current_revision,
            "table_count": len(tables),
            "expected_tables_present": expected_present,
            "all_expected_tables_present": all(expected_present.values()),
        }
    except Exception as exc:
        return {"inspected": False, "error_type": exc.__class__.__name__}


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 生产试点 PostgreSQL migration 演练",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', '')}",
        f"- execute_requested: {payload.get('execute_requested', False)}",
        f"- migration_executed: {payload.get('migration_executed', False)}",
        f"- database_connected: {payload.get('database_connected', False)}",
        f"- current_revision: {payload.get('database_inspection', {}).get('current_revision', '')}",
        "",
        "## 缺口",
        f"- missing_conditions: {json.dumps(payload.get('missing_conditions', []), ensure_ascii=False)}",
        f"- errors: {json.dumps(payload.get('errors', []), ensure_ascii=False)}",
        "",
        "## 边界声明",
    ]
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_production_migration_drill(
    *,
    output_dir: str | Path | None = None,
    execute: bool = False,
    command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    global_enabled = _env_enabled("PRODUCTION_MIGRATION_DRILL_ENABLED")
    storage_backend_postgres = str(os.getenv("STORAGE_BACKEND", "") or "").strip().lower() == "postgres"
    database_url_present = _env_present("DATABASE_URL")
    missing_conditions: list[str] = []
    errors: list[str] = []

    if not execute:
        status = "skipped"
        missing_conditions.append("cli:--execute_not_requested")
    elif not global_enabled or not storage_backend_postgres or not database_url_present:
        status = "blocked"
        if not global_enabled:
            missing_conditions.append("opt_in:PRODUCTION_MIGRATION_DRILL_ENABLED")
        if not storage_backend_postgres:
            missing_conditions.append("env:STORAGE_BACKEND_not_postgres")
        if not database_url_present:
            missing_conditions.append("env:DATABASE_URL")
    else:
        status = "success"

    alembic_result: dict[str, Any] = {"executed": False}
    migration_executed = False
    if status == "success":
        alembic_result = _run_alembic_upgrade(command_runner)
        alembic_result = {"executed": True, **alembic_result}
        migration_executed = alembic_result.get("returncode") == 0
        if not migration_executed:
            status = "failed"
            errors.append("alembic_upgrade_failed")

    inspection = _inspect_database() if database_url_present else {"inspected": False}
    database_connected = bool(inspection.get("inspected"))
    if migration_executed and not inspection.get("all_expected_tables_present"):
        status = "failed"
        errors.append("expected_tables_missing")

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "4.5.1",
        "phase": "v4.5 Phase 25.3 Controlled PostgreSQL Migration Drill",
        "mode": "execute_opt_in" if execute else "dry_run_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": not execute,
        "execute_requested": execute,
        "global_execute_enabled": global_enabled,
        "env_present": {
            "PRODUCTION_MIGRATION_DRILL_ENABLED": _env_present("PRODUCTION_MIGRATION_DRILL_ENABLED"),
            "STORAGE_BACKEND": _env_present("STORAGE_BACKEND"),
            "DATABASE_URL": database_url_present,
        },
        "migration_executed": migration_executed,
        "database_connected": database_connected,
        "redis_connected": False,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "alembic": _sanitize(alembic_result),
        "database_inspection": _sanitize(inspection),
        "missing_conditions": sorted(set(missing_conditions)),
        "errors": sorted(set(errors)),
        "go_no_go": {
            "migration_gate": "Manual-Review" if status == "success" else "Needs-Input",
            "public_production_direct_launch": "No-Go",
            "manual_signoff_required": True,
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    if _contains_secret_like_text(payload):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))
        payload["go_no_go"]["migration_gate"] = "Needs-Input"

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_production_migration_drill"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": payload["mode"],
        "read_only": payload["read_only"],
        "execute_requested": execute,
        "migration_executed": payload["migration_executed"],
        "database_connected": payload["database_connected"],
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "output_dir": str(output_root),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成或执行受控 PostgreSQL migration 演练报告")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true", help="执行 Alembic upgrade head；仍需 PRODUCTION_MIGRATION_DRILL_ENABLED=true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_migration_drill(output_dir=args.output_dir, execute=args.execute)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary["status"] in {"success", "skipped", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
