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

LOCAL_BUSINESS_VALUES = {
    "BUSINESS_INTEGRATION_ENABLED": "true",
    "BUSINESS_INTEGRATION_READ_ONLY": "true",
    "BUSINESS_INTEGRATION_WRITE_ENABLED": "false",
    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED": "true",
    "BUSINESS_INTEGRATION_AUDIT_REQUIRED": "true",
    "BUSINESS_SYSTEM_NAME": "local_business_read_mock",
    "BUSINESS_SYSTEM_BASE_URL_ENV": "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN_ENV": "BUSINESS_SYSTEM_TOKEN",
    "BUSINESS_SYSTEM_BASE_URL": "http://127.0.0.1:8765",
    "BUSINESS_SYSTEM_TOKEN": "local-business-read-token",
    "BUSINESS_SYSTEM_TOOL_ALLOWLIST": "business_read_probe",
    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST": "",
    "BUSINESS_SYSTEM_TIMEOUT_SECONDS": "5",
    "BUSINESS_SYSTEM_READ_PROBE_PATH": "/health",
    "BUSINESS_SYSTEM_AUTH_HEADER_NAME": "Authorization",
    "BUSINESS_SYSTEM_AUTH_SCHEME": "Bearer",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _is_gitignored_path(path: Path) -> bool:
    try:
        rel = str(path.resolve().relative_to(ROOT_DIR.resolve())).replace("\\", "/")
    except ValueError:
        return False
    try:
        result = subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(ROOT_DIR), text=True, capture_output=True, check=False)
    except Exception:
        return False
    return result.returncode == 0


def _merge_env(path: Path, updates: dict[str, str]) -> list[str]:
    raw_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    output: list[str] = []
    seen: set[str] = set()
    updated: list[str] = []
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


def build_production_landing_local_business_bootstrap(*, env_path: str | Path | None = None) -> dict[str, Any]:
    target = Path(env_path) if env_path else DEFAULT_ENV_PATH
    init_summary = build_production_landing_env_init(env_path=target)
    updated_keys = _merge_env(target, LOCAL_BUSINESS_VALUES)
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
        "updated_keys": [key for key in updated_keys if key not in {"BUSINESS_SYSTEM_BASE_URL", "BUSINESS_SYSTEM_TOKEN"}],
        "base_url_configured": True,
        "token_configured": True,
        "read_only": True,
        "write_enabled": False,
        "tool_allowlist": ["business_read_probe"],
        "requires_local_mock_server": True,
        "local_mock_command": "python scripts/local_business_read_mock_server.py",
        "next_commands": [
            "python scripts/local_business_read_mock_server.py",
            "python scripts/production_landing_env_check.py",
            "python scripts/production_landing_env_runner.py --action local-business-smoke",
        ],
        "secret_plaintext_output": False,
        "contains_real_secret": False,
        "public_production_direct_launch": "No-Go",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap local-only business read mock env values.")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_local_business_bootstrap(env_path=args.env_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
