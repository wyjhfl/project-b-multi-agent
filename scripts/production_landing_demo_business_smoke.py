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
from scripts.demo_business_read_server import EXPECTED_TOKEN_ENV, Handler
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


def _port_from_base_url(base_url: str, default: int = 8876) -> int:
    try:
        return int(base_url.rsplit(":", 1)[1].split("/", 1)[0])
    except Exception:
        return default


def build_production_landing_demo_business_smoke(
    *,
    output_dir: str | Path | None = None,
    env_path: str | Path | None = None,
) -> dict:
    host = "127.0.0.1"
    path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    env_values = _parse_env_file(path)
    base_url = env_values.get("BUSINESS_SYSTEM_BASE_URL", "http://127.0.0.1:8876")
    port = _port_from_base_url(base_url)
    token = env_values.get("BUSINESS_SYSTEM_TOKEN", "demo-business-read-token")
    runtime_values = {
        **env_values,
        "BUSINESS_SYSTEM_NAME": env_values.get("BUSINESS_SYSTEM_NAME", "demo_business_system"),
        "BUSINESS_SYSTEM_BASE_URL": base_url,
        "BUSINESS_SYSTEM_TOKEN": token,
        EXPECTED_TOKEN_ENV: token,
        "DEMO_BUSINESS_SYSTEM_PORT": str(port),
    }
    original_env = {key: os.environ.get(key) for key in runtime_values}
    os.environ.update(runtime_values)
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ready = _wait_until_ready(host, port)
        if not ready:
            return {
                "status": "failed",
                "demo_server_ready": False,
                "demo_business_system_used": True,
                "business_system_connected": False,
                "business_read_executed": False,
                "secret_plaintext_output": False,
                "env_file_present": path.exists(),
            }
        summary = build_business_system_read_smoke(
            output_dir=output_dir or DEFAULT_OUTPUT_DIR,
            execute=True,
            local_business_mock_used=False,
            demo_business_system_used=True,
        )
        summary["demo_server_ready"] = True
        summary["demo_business_system_used"] = True
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
    parser = argparse.ArgumentParser(description="Run controlled demo business read-only server and smoke.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_demo_business_smoke(output_dir=args.output_dir, env_path=args.env_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("json_path"):
        print(f"json_path={summary['json_path']}")
    if summary.get("markdown_path"):
        print(f"markdown_path={summary['markdown_path']}")
    return 0 if summary.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
