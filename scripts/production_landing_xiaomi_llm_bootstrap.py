from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.production_landing_env_init import DEFAULT_ENV_PATH, build_production_landing_env_init

XIAOMI_API_KEY_ENV = "XIAOMI_LLM_API_KEY"
XIAOMI_LLM_VALUES = {
    "REAL_INTEGRATION_STAGING_SMOKE_ENABLED": "true",
    "REAL_LLM_STAGING_SMOKE_EXECUTE": "true",
    "REAL_LLM_ACCEPTANCE_ENABLED": "true",
    "REAL_LLM_PREFLIGHT_ENABLED": "true",
    "REAL_LLM_SMOKE_ENABLED": "true",
    "REAL_LLM_PREFLIGHT_NETWORK_CHECK": "true",
    "REAL_LLM_PROVIDER": "litellm",
    "REAL_LLM_MODEL": "mimo-v2.5-pro",
    "REAL_LLM_BASE_URL": "https://token-plan-cn.xiaomimimo.com/v1",
    "REAL_LLM_API_KEY_ENV": XIAOMI_API_KEY_ENV,
}


def _codex_python(command: str) -> str:
    if command.startswith("python scripts/"):
        return "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 " + command.removeprefix(
            "python "
        ).replace("/", "\\")
    if command.startswith("python -m "):
        return "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 " + command.removeprefix(
            "python "
        )
    return command


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


def _merge_env(path: Path, updates: dict[str, str]) -> list[str]:
    raw_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    updated: list[str] = []
    output: list[str] = []
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
            updated.append(key)
        else:
            output.append(raw_line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
            updated.append(key)
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return updated


def _has_non_placeholder(value: str) -> bool:
    text = (value or "").strip()
    return bool(text and not (text.startswith("<") and text.endswith(">")))


def build_production_landing_xiaomi_llm_bootstrap(
    *,
    env_path: str | Path | None = None,
    copy_process_key: bool = True,
    overwrite_existing_key: bool = False,
) -> dict[str, Any]:
    target = Path(env_path) if env_path else DEFAULT_ENV_PATH
    init_summary = build_production_landing_env_init(env_path=target)
    before = _parse_env_file(target)
    updates = dict(XIAOMI_LLM_VALUES)

    process_key_present = _has_non_placeholder(os.getenv(XIAOMI_API_KEY_ENV, ""))
    local_key_present_before = _has_non_placeholder(before.get(XIAOMI_API_KEY_ENV, ""))
    key_copied_from_process_env = False
    key_preserved = False

    if copy_process_key and process_key_present and (overwrite_existing_key or not local_key_present_before):
        updates[XIAOMI_API_KEY_ENV] = str(os.getenv(XIAOMI_API_KEY_ENV, "") or "").strip()
        key_copied_from_process_env = True
    elif local_key_present_before:
        key_preserved = True
    else:
        updates[XIAOMI_API_KEY_ENV] = "<secret-managed-token>"

    updated_keys = _merge_env(target, updates)
    after = _parse_env_file(target)
    local_key_present_after = _has_non_placeholder(after.get(XIAOMI_API_KEY_ENV, ""))
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
        "updated_keys": [key for key in updated_keys if key != XIAOMI_API_KEY_ENV],
        "api_key_env": XIAOMI_API_KEY_ENV,
        "process_api_key_present": process_key_present,
        "local_api_key_present_before": local_key_present_before,
        "local_api_key_present_after": local_key_present_after,
        "api_key_copied_from_process_env": key_copied_from_process_env,
        "api_key_preserved": key_preserved,
        "real_llm_model": "mimo-v2.5-pro",
        "real_llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "next_commands": [
            _codex_python("python scripts/production_landing_env_check.py"),
            _codex_python("python scripts/production_landing_execution_gate.py"),
            _codex_python("python scripts/production_landing_env_runner.py --action env-check"),
        ],
        "secret_plaintext_output": False,
        "contains_real_secret": False,
        "public_production_direct_launch": "No-Go",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap local-only Xiaomi OpenAI-compatible LLM env values.")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--no-copy-process-key", action="store_true")
    parser.add_argument("--overwrite-existing-key", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_xiaomi_llm_bootstrap(
        env_path=args.env_path,
        copy_process_key=not args.no_copy_process_key,
        overwrite_existing_key=args.overwrite_existing_key,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
