from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.business_system_read_smoke import DEFAULT_OUTPUT_DIR, build_business_system_read_smoke
from scripts.local_business_read_mock_server import Handler
from scripts.production_landing_env_init import DEFAULT_ENV_PATH


BUSINESS_ENV_KEYS = {
    "BUSINESS_INTEGRATION_ENABLED",
    "BUSINESS_INTEGRATION_READ_ONLY",
    "BUSINESS_INTEGRATION_WRITE_ENABLED",
    "BUSINESS_INTEGRATION_APPROVAL_REQUIRED",
    "BUSINESS_INTEGRATION_AUDIT_REQUIRED",
    "BUSINESS_SYSTEM_NAME",
    "BUSINESS_SYSTEM_BASE_URL_ENV",
    "BUSINESS_SYSTEM_TOKEN_ENV",
    "BUSINESS_SYSTEM_BASE_URL",
    "BUSINESS_SYSTEM_TOKEN",
    "BUSINESS_SYSTEM_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST",
    "BUSINESS_SYSTEM_TIMEOUT_SECONDS",
    "BUSINESS_SYSTEM_READ_PROBE_PATH",
    "BUSINESS_SYSTEM_AUTH_HEADER_NAME",
    "BUSINESS_SYSTEM_AUTH_SCHEME",
}


def _wait_until_ready(host: str, port: int, timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in BUSINESS_ENV_KEYS:
            values[key] = value.strip().strip("\"'")
    return values


def build_production_landing_local_business_smoke(
    *,
    output_dir: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict:
    host = "127.0.0.1"
    port = 8765
    path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    env_values = _parse_env_file(path)
    original_env = {key: os.environ.get(key) for key in env_values}
    os.environ.update(env_values)
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ready = _wait_until_ready(host, port)
        if not ready:
            return {
                "status": "failed",
                "mock_server_ready": False,
                "business_system_connected": False,
                "business_read_executed": False,
                "secret_plaintext_output": False,
                "env_file_present": path.exists(),
            }
        summary = build_business_system_read_smoke(
            output_dir=output_dir or DEFAULT_OUTPUT_DIR,
            execute=True,
            local_business_mock_used=True,
        )
        summary["mock_server_ready"] = True
        summary["env_file_present"] = path.exists()
        summary["env_key_count"] = len(env_values)
        summary["secret_plaintext_output"] = False
        return summary
    finally:
        server.shutdown()
        server.server_close()
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local business read mock server and execute business read smoke.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_local_business_smoke(output_dir=args.output_dir, env_path=args.env_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("json_path"):
        print(f"json_path={summary['json_path']}")
    if summary.get("markdown_path"):
        print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
