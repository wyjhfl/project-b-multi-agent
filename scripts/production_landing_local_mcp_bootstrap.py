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

FAKE_MCP_SERVER = ROOT_DIR / "scripts" / "local_fake_mcp_stdio_server.py"


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


def build_production_landing_local_mcp_bootstrap(*, env_path: str | Path | None = None) -> dict[str, Any]:
    target = Path(env_path) if env_path else DEFAULT_ENV_PATH
    init_summary = build_production_landing_env_init(env_path=target)
    command = sys.executable
    updates = {
        "MCP_STAGING_SMOKE_EXECUTE": "true",
        "MCP_MODE": "real",
        "MCP_SERVER_COMMAND": command,
        "MCP_SERVER_ARGS": f"{str(FAKE_MCP_SERVER).replace('\\', '/')} normal",
        "MCP_SERVER_WORKDIR": str(ROOT_DIR),
        "MCP_SERVER_ENV_ALLOWLIST": "",
        "MCP_SERVER_COMMAND_ALLOWLIST": command,
        "MCP_TOOL_ALLOWLIST": "stdio_date_lookup",
        "MCP_SERVER_TIMEOUT_SECONDS": "10",
    }
    updated_keys = _merge_env(target, updates)
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
        "mcp_server_fixture_present": FAKE_MCP_SERVER.exists(),
        "mcp_command_configured": True,
        "mcp_command_allowlist_configured": True,
        "mcp_tool_allowlist": ["stdio_date_lookup"],
        "next_commands": [
            "python scripts/production_landing_env_check.py",
            "python scripts/production_landing_execution_gate.py",
            "python scripts/production_landing_env_runner.py --action staging-smoke",
        ],
        "secret_plaintext_output": False,
        "contains_real_secret": False,
        "public_production_direct_launch": "No-Go",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap local-only controlled MCP stdio env values.")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_local_mcp_bootstrap(env_path=args.env_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
