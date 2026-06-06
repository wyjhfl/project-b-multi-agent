from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.production_landing_env_init import DEFAULT_ENV_PATH, build_production_landing_env_init

LOCAL_INFRA_VALUES = {
    "POSTGRES_STAGING_SMOKE_EXECUTE": "true",
    "STORAGE_BACKEND": "postgres",
    "DATABASE_URL": "postgresql+psycopg://agent:dev-only-password@localhost:5432/project_b",
    "REDIS_STAGING_SMOKE_EXECUTE": "true",
    "REDIS_ENABLED": "true",
    "REDIS_URL": "redis://localhost:6379/0",
    "RATE_LIMIT_BACKEND": "redis",
}

SECRET_VALUE_KEYS = {"DATABASE_URL", "REDIS_URL"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _is_gitignored_path(path: Path) -> bool:
    try:
        rel = str(path.resolve().relative_to(ROOT_DIR.resolve())).replace("\\", "/")
    except ValueError:
        return False
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=str(ROOT_DIR),
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def _write_merged_env(path: Path, updates: dict[str, str]) -> list[str]:
    raw_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    updated_keys: list[str] = []

    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            output.append(raw_line)
            continue
        key, _ = raw_line.split("=", 1)
        key = key.strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
            updated_keys.append(key)
        else:
            output.append(raw_line)

    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
            updated_keys.append(key)

    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return updated_keys


def build_production_landing_local_infra_bootstrap(
    *,
    env_path: str | Path | None = None,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    target = Path(env_path) if env_path else DEFAULT_ENV_PATH
    init_summary = build_production_landing_env_init(env_path=target)
    before = _parse_env_file(target)
    updates: dict[str, str] = {}
    skipped_existing: list[str] = []

    for key, value in LOCAL_INFRA_VALUES.items():
        current = before.get(key, "")
        if current and not current.startswith("<") and key in SECRET_VALUE_KEYS and not overwrite_existing:
            skipped_existing.append(key)
            continue
        updates[key] = value

    updated_keys = _write_merged_env(target, updates) if updates else []
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    gitignored = _is_gitignored_path(target)
    return {
        "status": "success" if gitignored else "partial",
        "generated_at": generated_at,
        "commit": commit,
        "env_path": str(target),
        "env_file_present": target.exists(),
        "env_initialized": bool(init_summary.get("env_file_present", False)),
        "gitignored": gitignored,
        "updated_keys": updated_keys,
        "updated_secret_value_keys": [key for key in updated_keys if key in SECRET_VALUE_KEYS],
        "skipped_existing_secret_value_keys": skipped_existing,
        "postgres_local_compose_ready": "DATABASE_URL" in updated_keys or "DATABASE_URL" in skipped_existing,
        "redis_local_compose_ready": "REDIS_URL" in updated_keys or "REDIS_URL" in skipped_existing,
        "requires_docker_compose_services": ["postgres", "redis"],
        "next_commands": [
            "docker compose up -d postgres redis",
            "python scripts/production_landing_env_check.py",
            "python scripts/production_landing_execution_gate.py",
        ],
        "secret_plaintext_output": False,
        "contains_real_secret": False,
        "public_production_direct_launch": "No-Go",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap local-only Postgres/Redis staging env values.")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--overwrite-existing", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_local_infra_bootstrap(
        env_path=args.env_path,
        overwrite_existing=args.overwrite_existing,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
