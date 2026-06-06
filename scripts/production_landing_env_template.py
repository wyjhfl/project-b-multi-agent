from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = ROOT_DIR / "local" / "production_landing.staging.env.template"

SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\xiaomi_llm_preflight.ps1"
SAFE_BUSINESS_READ_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\business_system_read_smoke.ps1"
SAFE_POSTGRES_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains postgres"
SAFE_REDIS_INFRA_SMOKE_COMMAND = "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 -Domains redis"
SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND = (
    "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\real_integration_infra_smoke.ps1 "
    "-Domains external_mcp -McpServerCommand <approved-command> "
    "-McpServerCommandAllowlist <approved-command> -McpToolAllowlist <approved-tools>"
)
SAFE_INFRA_AND_LLM_SMOKE_COMMAND = " ; ".join(
    [
        SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND,
        SAFE_POSTGRES_INFRA_SMOKE_COMMAND,
        SAFE_REDIS_INFRA_SMOKE_COMMAND,
        SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND,
    ]
)


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
    gitignore_path = ROOT_DIR / ".gitignore"
    if rel.startswith("local/") and gitignore_path.exists():
        ignored_patterns = {
            line.strip().rstrip("/")
            for line in gitignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        if "local" in ignored_patterns:
            return True
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


def _template_lines() -> list[str]:
    return [
        "# Project B controlled staging landing env template",
        "# Copy values into a local secret-managed environment. Do not commit real secrets.",
        "",
        "APP_ENV=staging",
        "AUTH_ENABLED=true",
        "RBAC_ENABLED=true",
        "",
        "# Real LLM: Xiaomi OpenAI-compatible endpoint",
        "REAL_INTEGRATION_STAGING_SMOKE_ENABLED=true",
        "REAL_LLM_STAGING_SMOKE_EXECUTE=true",
        "REAL_LLM_ACCEPTANCE_ENABLED=true",
        "REAL_LLM_PREFLIGHT_ENABLED=true",
        "REAL_LLM_SMOKE_ENABLED=true",
        "REAL_LLM_PREFLIGHT_NETWORK_CHECK=true",
        "REAL_LLM_PROVIDER=litellm",
        "REAL_LLM_MODEL=mimo-v2.5-pro",
        "REAL_LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1",
        "REAL_LLM_API_KEY_ENV=XIAOMI_LLM_API_KEY",
        "XIAOMI_LLM_API_KEY=<secret-managed-token>",
        "",
        "# PostgreSQL staging storage",
        "POSTGRES_STAGING_SMOKE_EXECUTE=true",
        "STORAGE_BACKEND=postgres",
        "DATABASE_URL=<secret-managed-url>",
        "",
        "# Redis staging rate limit/cache",
        "REDIS_STAGING_SMOKE_EXECUTE=true",
        "REDIS_ENABLED=true",
        "REDIS_URL=<secret-managed-url>",
        "RATE_LIMIT_BACKEND=redis",
        "",
        "# External MCP staging server",
        "MCP_STAGING_SMOKE_EXECUTE=true",
        "MCP_MODE=real",
        "MCP_SERVER_COMMAND=<approved-command>",
        "MCP_SERVER_ARGS=",
        "MCP_SERVER_WORKDIR=",
        "MCP_SERVER_ENV_ALLOWLIST=<approved-env-names>",
        "MCP_SERVER_COMMAND_ALLOWLIST=<approved-command>",
        "MCP_TOOL_ALLOWLIST=<approved-tools>",
        "MCP_SERVER_TIMEOUT_SECONDS=10",
        "",
        "# Business system read-only probe",
        "BUSINESS_INTEGRATION_ENABLED=true",
        "BUSINESS_INTEGRATION_READ_ONLY=true",
        "BUSINESS_INTEGRATION_WRITE_ENABLED=false",
        "BUSINESS_INTEGRATION_APPROVAL_REQUIRED=true",
        "BUSINESS_INTEGRATION_AUDIT_REQUIRED=true",
        "BUSINESS_SYSTEM_BASE_URL_ENV=BUSINESS_SYSTEM_BASE_URL",
        "BUSINESS_SYSTEM_TOKEN_ENV=BUSINESS_SYSTEM_TOKEN",
        "BUSINESS_SYSTEM_BASE_URL=<secret-managed-url>",
        "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>",
        "BUSINESS_SYSTEM_TOOL_ALLOWLIST=business_read_probe",
        "BUSINESS_SYSTEM_WRITE_TOOL_ALLOWLIST=",
        "BUSINESS_SYSTEM_TIMEOUT_SECONDS=5",
        "BUSINESS_SYSTEM_READ_PROBE_PATH=/health",
        "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization",
        "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer",
        "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>",
        "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>",
        "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>",
        "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>",
        "",
        "# After filling real values in a local secret manager/process env, run:",
        f"# {SAFE_XIAOMI_LLM_PREFLIGHT_COMMAND}",
        f"# {SAFE_POSTGRES_INFRA_SMOKE_COMMAND}",
        f"# {SAFE_REDIS_INFRA_SMOKE_COMMAND}",
        f"# {SAFE_EXTERNAL_MCP_INFRA_SMOKE_COMMAND}",
        f"# {SAFE_BUSINESS_READ_SMOKE_COMMAND}",
    ]


def build_production_landing_env_template(*, output_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _template_lines()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ignored = _is_gitignored_path(path)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    return {
        "status": "success" if ignored else "partial",
        "generated_at": generated_at,
        "commit": commit,
        "template_path": str(path),
        "gitignored": ignored,
        "secret_plaintext_output": False,
        "contains_real_secret": False,
        "real_llm_model": "mimo-v2.5-pro",
        "real_llm_base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "staging_smoke_command": SAFE_INFRA_AND_LLM_SMOKE_COMMAND,
        "business_smoke_command": SAFE_BUSINESS_READ_SMOKE_COMMAND,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate local-only production landing env template.")
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_production_landing_env_template(output_path=args.output_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"template_path={summary['template_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
