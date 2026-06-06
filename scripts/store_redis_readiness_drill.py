from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "store_redis_readiness_drill"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

BOUNDARY_DECLARATIONS = [
    "只读 Store and Redis production readiness drill",
    "仅检查 env name、present 布尔状态、本地代码文件、迁移文件和测试文件存在性",
    "不连接真实 PostgreSQL",
    "不连接真实 Redis",
    "不执行 Alembic migration",
    "不写入业务数据、审计数据或指标数据",
    "不读取或输出 DATABASE_URL、REDIS_URL、JWT_SECRET 等 secret 原文",
    "默认 storage_backend=sqlite、redis_enabled=false，离线开发路径保持不变",
    "PostgreSQL 与 Redis 仅在显式 opt-in 和人工受控条件下进入真实验收",
    "不宣称 PostgreSQL、Redis 或多实例限流生产验收完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _env_enabled(key: str) -> bool:
    return str(os.getenv(key, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_presence(keys: list[str]) -> dict[str, dict[str, Any]]:
    return {key: {"present": bool(os.getenv(key))} for key in keys}


def _env_value_equals(key: str, expected: str) -> bool:
    return (os.getenv(key, "") or "").strip().lower() == expected.lower()


def _path_exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _local_checks() -> dict[str, dict[str, Any]]:
    paths = {
        "store_factory": "app/storage/factory.py",
        "storage_database": "app/storage/database.py",
        "storage_models": "app/storage/models.py",
        "sqlite_task_store": "app/storage/task_store.py",
        "sqlite_approval_store": "app/storage/approval_store.py",
        "sqlite_audit_store": "app/storage/audit_store.py",
        "sqlite_metrics_store": "app/harness/metrics/metrics_store.py",
        "postgres_task_store": "app/storage/postgres/task_store.py",
        "postgres_user_store": "app/storage/postgres/user_store.py",
        "postgres_approval_store": "app/storage/postgres/approval_store.py",
        "postgres_audit_store": "app/storage/postgres/audit_store.py",
        "postgres_metrics_store": "app/storage/postgres/metrics_store.py",
        "postgres_graph_checkpoint_store": "app/storage/postgres/graph_checkpoint_store.py",
        "redis_client": "app/cache/redis_client.py",
        "request_guards": "app/core/request_guards.py",
        "deployment_guard": "app/core/deployment_guard.py",
        "app_main": "app/main.py",
        "alembic_ini": "alembic.ini",
        "alembic_env": "alembic/env.py",
        "docker_compose": "docker-compose.yml",
        "prod_compose": "docker-compose.prod.yml",
        "storage_tests": "tests/test_storage_v20.py",
        "config_tests": "tests/test_config_v20.py",
        "deployment_guard_tests": "tests/test_deployment_guard_v60.py",
        "request_guard_tests": "tests/test_request_guards_v72.py",
        "runtime_persistence_tests": "tests/test_runtime_persistence_v05.py",
        "audit_tests": "tests/test_audit_v045.py",
    }
    return {key: {"path": path, "present": _path_exists(path)} for key, path in paths.items()}


def _alembic_migration_index() -> dict[str, Any]:
    versions_dir = ROOT_DIR / "alembic" / "versions"
    if not versions_dir.exists():
        return {
            "path": "alembic/versions",
            "exists": False,
            "status": "skipped",
            "missing_conditions": ["local:alembic_versions"],
            "migration_files": [],
            "migration_count": 0,
            "migration_executed": False,
        }
    files = sorted(item.name for item in versions_dir.glob("*.py") if item.is_file())
    return {
        "path": "alembic/versions",
        "exists": True,
        "status": "partial" if files else "skipped",
        "missing_conditions": [] if files else ["local:alembic_versions_empty"],
        "migration_files": files,
        "migration_count": len(files),
        "migration_executed": False,
    }


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _missing_local(local: dict[str, dict[str, Any]], keys: list[str]) -> list[str]:
    return [f"local:{key}" for key in keys if not local.get(key, {}).get("present")]


def _check(
    check_id: str,
    *,
    status: str,
    missing_conditions: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
    risk_notes: list[str] | None = None,
    recommended_actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "missing_conditions": sorted(set(missing_conditions or [])),
        "evidence": evidence or {},
        "risk_notes": risk_notes or [],
        "recommended_actions": recommended_actions or [],
    }


def _acceptance_checks(local: dict[str, dict[str, Any]], migrations: dict[str, Any]) -> list[dict[str, Any]]:
    storage_backend_postgres = _env_value_equals("STORAGE_BACKEND", "postgres")
    database_url_present = bool(os.getenv("DATABASE_URL"))
    redis_enabled = _env_enabled("REDIS_ENABLED")
    redis_url_present = bool(os.getenv("REDIS_URL"))

    store_factory_required = [
        "store_factory",
        "storage_database",
        "storage_models",
        "postgres_task_store",
        "postgres_user_store",
        "postgres_approval_store",
        "postgres_audit_store",
        "postgres_metrics_store",
        "postgres_graph_checkpoint_store",
        "storage_tests",
    ]
    sqlite_required = [
        "sqlite_task_store",
        "sqlite_approval_store",
        "sqlite_audit_store",
        "sqlite_metrics_store",
        "config_tests",
    ]
    redis_required = ["redis_client", "request_guards", "deployment_guard", "config_tests", "request_guard_tests"]
    audit_metrics_required = ["sqlite_audit_store", "sqlite_metrics_store", "postgres_audit_store", "postgres_metrics_store", "runtime_persistence_tests", "audit_tests"]

    return [
        _check(
            "postgres_store_opt_in_config",
            status="partial" if storage_backend_postgres and database_url_present else "skipped",
            missing_conditions=(
                ([] if storage_backend_postgres else ["env:STORAGE_BACKEND_not_postgres"])
                + ([] if database_url_present else ["env:DATABASE_URL"])
            ),
            evidence={
                "env": _env_presence(["STORAGE_BACKEND", "DATABASE_URL"]),
                "storage_backend_expected": "postgres",
                "database_connected": False,
            },
            risk_notes=["默认 storage_backend=sqlite；PostgreSQL 真实验收必须显式配置并通过部署门禁。"],
        ),
        _check(
            "store_factory_and_postgres_stores",
            status="partial" if not _missing_local(local, store_factory_required) else "skipped",
            missing_conditions=_missing_local(local, store_factory_required),
            evidence={key: local[key] for key in store_factory_required if key in local},
            recommended_actions=["真实数据库演练前继续保持 Store Factory 统一入口，不绕过 app.main 主链路。"],
        ),
        _check(
            "sqlite_default_fallback_preserved",
            status="partial" if not _missing_local(local, sqlite_required) else "skipped",
            missing_conditions=_missing_local(local, sqlite_required),
            evidence={key: local[key] for key in sqlite_required if key in local},
            risk_notes=["默认离线演示路径必须保留 SQLite，不得强制依赖 PostgreSQL。"],
        ),
        _check(
            "alembic_migration_precheck",
            status=migrations["status"],
            missing_conditions=migrations["missing_conditions"],
            evidence=migrations,
            recommended_actions=["真实生产迁移必须另行执行人工受控演练；本脚本不运行 Alembic。"],
        ),
        _check(
            "redis_opt_in_config",
            status="partial" if redis_enabled and redis_url_present else "skipped",
            missing_conditions=(
                ([] if redis_enabled else ["opt_in:REDIS_ENABLED_not_enabled"])
                + ([] if redis_url_present else ["env:REDIS_URL"])
            ),
            evidence={
                "env": _env_presence(["REDIS_ENABLED", "REDIS_URL"]),
                "redis_connected": False,
                "redis_write_executed": False,
            },
            risk_notes=["默认 REDIS_ENABLED=false；本脚本不 ping Redis、不执行写入。"],
        ),
        _check(
            "noop_redis_fallback",
            status="partial" if not _missing_local(local, redis_required) else "skipped",
            missing_conditions=_missing_local(local, redis_required),
            evidence={key: local[key] for key in redis_required if key in local},
            risk_notes=["Redis 连接失败时应 fallback 到 NoopRedisClient；多实例限流仍需 Redis 或网关级限流。"],
        ),
        _check(
            "rate_limit_storage_boundary",
            status="partial" if local["request_guards"]["present"] and local["request_guard_tests"]["present"] else "skipped",
            missing_conditions=_missing_local(local, ["request_guards", "request_guard_tests"]),
            evidence={
                "request_guards": local["request_guards"],
                "request_guard_tests": local["request_guard_tests"],
                "default_rate_limiter": "memory",
                "redis_rate_limit_backend_available": True,
                "redis_rate_limit_store_verified": False,
            },
            risk_notes=["当前默认限流后端仍为 memory；Redis backend 已具备 opt-in 路径，但多实例生产仍需真实 Redis 或网关级限流验收证据。"],
        ),
        _check(
            "deployment_guard_store_redis_checks",
            status="partial" if local["deployment_guard"]["present"] and local["deployment_guard_tests"]["present"] else "skipped",
            missing_conditions=_missing_local(local, ["deployment_guard", "deployment_guard_tests"]),
            evidence={
                "deployment_guard": local["deployment_guard"],
                "deployment_guard_tests": local["deployment_guard_tests"],
                "docker_compose": local["docker_compose"],
                "prod_compose": local["prod_compose"],
            },
            recommended_actions=["生产配置必须先通过 deployment guard；配置错误应返回结构化结果，不抛 500。"],
        ),
        _check(
            "audit_metrics_store_boundary",
            status="partial" if not _missing_local(local, audit_metrics_required) else "skipped",
            missing_conditions=_missing_local(local, audit_metrics_required),
            evidence={key: local[key] for key in audit_metrics_required if key in local},
            risk_notes=["审计和指标存储可走 SQLite 或 PostgreSQL Store；本脚本不写审计或指标数据。"],
        ),
        _check(
            "compose_readiness_files",
            status="partial" if local["docker_compose"]["present"] and local["prod_compose"]["present"] else "skipped",
            missing_conditions=_missing_local(local, ["docker_compose", "prod_compose"]),
            evidence={"docker_compose": local["docker_compose"], "prod_compose": local["prod_compose"]},
            recommended_actions=["真实演练前继续用 docker compose config 和 prod override config 做结构校验。"],
        ),
    ]


def _derive_status(checks: list[dict[str, Any]], local: dict[str, dict[str, Any]]) -> str:
    if any(check["status"] == "blocked" for check in checks):
        return "blocked"
    if any(not item["present"] for item in local.values()):
        return "skipped"
    if any(check["status"] == "skipped" for check in checks):
        return "skipped"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.7 Store and Redis production readiness drill（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- database_connected: {payload.get('database_connected', False)}",
        f"- redis_connected: {payload.get('redis_connected', False)}",
        f"- migration_executed: {payload.get('migration_executed', False)}",
        "",
        "## 门禁项",
    ]
    for check in payload.get("acceptance_checks", []):
        lines.extend(
            [
                f"### {check['check_id']}",
                f"- status: {check['status']}",
                f"- missing_conditions: {json.dumps(check.get('missing_conditions', []), ensure_ascii=False)}",
                "",
            ]
        )
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_store_redis_readiness_drill(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    local = _local_checks()
    migrations = _alembic_migration_index()
    checks = _acceptance_checks(local, migrations)
    missing_conditions = sorted({item for check in checks for item in check.get("missing_conditions", [])})
    status = _derive_status(checks, local)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.7.0",
        "phase": "v3.7 Phase 17.4",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "database_connected": False,
        "redis_connected": False,
        "migration_executed": False,
        "business_data_written": False,
        "audit_data_written": False,
        "metrics_data_written": False,
        "secret_plaintext_output": False,
        "env": _env_presence(["STORAGE_BACKEND", "DATABASE_URL", "REDIS_ENABLED", "REDIS_URL"]),
        "local_checks": local,
        "alembic_migration_index": migrations,
        "acceptance_checks": checks,
        "check_count": len(checks),
        "missing_conditions": missing_conditions,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "recommended_next_actions": [
            "真实 PostgreSQL/Redis 演练前必须显式 opt-in，并先通过 deployment guard。",
            "多实例限流需补 Redis 或网关级限流验收证据，不能用进程内限流替代生产验收。",
            "Phase 17.5 可继续推进 Business system integration safety checklist。",
        ],
        "output_dir": str(output_root),
    }
    if _contains_secret_like_text(json.dumps(payload, ensure_ascii=False)):
        payload["status"] = "blocked"
        payload["secret_plaintext_output"] = False
        payload["missing_conditions"] = sorted(set(payload["missing_conditions"] + ["output:secret_like_text_detected"]))

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_store_redis_readiness_drill"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": payload["status"],
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "database_connected": False,
        "redis_connected": False,
        "migration_executed": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "check_count": len(checks),
        "missing_count": len(payload["missing_conditions"]),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.7 Store and Redis production readiness drill（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_store_redis_readiness_drill(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
