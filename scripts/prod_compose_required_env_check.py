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
DEFAULT_COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")
REQUIRED_ENV_KEYS = ("DATABASE_URL", "REDIS_URL", "JWT_SECRET")
COMPOSE_COMMAND = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml", "config"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_tail(text: str, max_lines: int = 20) -> list[str]:
    return (text or "").splitlines()[-max_lines:]


def _mentions_required_env_error(text: str, required_env_keys: tuple[str, ...]) -> bool:
    lower_text = text.lower()
    mentions_key = any(key in text for key in required_env_keys)
    if not mentions_key:
        return False
    mentions_required = (
        "required variable" in lower_text
        or " is required" in lower_text
        or "missing a value" in lower_text
        or "interpolating" in lower_text
        or "variable is not set" in lower_text
        or "parameter is unset" in lower_text
    )
    expected_messages = [
        f"{key} is required".lower()
        for key in required_env_keys
    ]
    return mentions_required or any(message in lower_text for message in expected_messages)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_required_interpolation(text: str, key: str) -> bool:
    pattern = re.compile(r"\$\{\s*" + re.escape(key) + r"\s*:\?")
    return bool(pattern.search(text))


def build_prod_compose_required_env_check(
    *,
    root_dir: str | Path | None = None,
    execute: bool = True,
    required_env_keys: tuple[str, ...] = REQUIRED_ENV_KEYS,
) -> dict[str, Any]:
    root = Path(root_dir) if root_dir is not None else ROOT_DIR
    generated_at = _utc_now_iso()
    prod_compose_path = root / "docker-compose.prod.yml"
    missing_conditions: list[str] = []
    required_interpolations: dict[str, bool] = {}

    if not prod_compose_path.exists():
        missing_conditions.append("compose:prod_override_missing")
        prod_text = ""
    else:
        prod_text = _read_text(prod_compose_path)

    for key in required_env_keys:
        present = _has_required_interpolation(prod_text, key)
        required_interpolations[key] = present
        if not present:
            missing_conditions.append(f"compose:{key}_required_interpolation_missing")

    compose_executed = False
    compose_return_code: int | None = None
    stderr_tail: list[str] = []
    stdout_tail: list[str] = []
    env_restored = True

    if execute and not missing_conditions:
        original_values = {key: os.environ.get(key) for key in required_env_keys}
        try:
            for key in required_env_keys:
                os.environ.pop(key, None)
            completed = subprocess.run(
                COMPOSE_COMMAND,
                cwd=str(root),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=60,
            )
            compose_executed = True
            compose_return_code = completed.returncode
            stdout_tail = _safe_tail(completed.stdout)
            stderr_tail = _safe_tail(completed.stderr)
            if completed.returncode == 0:
                missing_conditions.append("compose:prod_config_succeeded_without_required_env")
            elif not _mentions_required_env_error(
                f"{completed.stdout}\n{completed.stderr}",
                required_env_keys,
            ):
                missing_conditions.append("compose:prod_config_failed_without_required_env_error")
        finally:
            for key, value in original_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            env_restored = all(os.environ.get(key) == value for key, value in original_values.items())

    status = "success" if not missing_conditions else "blocked"
    return {
        "generated_at": generated_at,
        "status": status,
        "mode": "read_only_prod_compose_required_env_check",
        "compose_files": list(DEFAULT_COMPOSE_FILES),
        "required_env_keys": list(required_env_keys),
        "required_interpolations": required_interpolations,
        "execute": execute,
        "compose_executed": compose_executed,
        "compose_return_code": compose_return_code,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "missing_conditions": missing_conditions,
        "env_restored": env_restored,
        "secret_plaintext_output": False,
        "public_production_direct_launch": "No-Go",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check that prod compose override fails closed when required env is missing."
    )
    parser.add_argument("--root-dir", default=str(ROOT_DIR))
    parser.add_argument("--no-execute", action="store_true", help="Only inspect compose interpolation syntax.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    payload = build_prod_compose_required_env_check(
        root_dir=args.root_dir,
        execute=not bool(args.no_execute),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
