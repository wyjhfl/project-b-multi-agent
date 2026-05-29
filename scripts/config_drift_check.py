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

from app.core.config import Settings

DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "config_drift"
ENV_EXAMPLE_PATH = ROOT_DIR / ".env.example"
ENV_PRODUCTION_EXAMPLE_PATH = ROOT_DIR / ".env.production.example"

COMPOSE_REQUIRED_ENV = ["JWT_SECRET", "DATABASE_URL", "REDIS_URL"]

DEPLOYMENT_GUARD_RELATED = [
    "APP_ENV",
    "JWT_SECRET",
    "AUTH_ENABLED",
    "RBAC_ENABLED",
    "CORS_ALLOW_ORIGINS",
    "SECURITY_HEADERS_ENABLED",
    "STRUCTURED_LOGGING_ENABLED",
    "LOG_REDACTION_ENABLED",
    "LOG_LEVEL",
    "AUDIT_RETENTION_ENABLED",
    "AUDIT_RETENTION_DAYS",
    "AUDIT_EXPORT_MAX_ROWS",
    "AUDIT_EXPORT_REDACTION_ENABLED",
    "REQUEST_SIZE_LIMIT_ENABLED",
    "REQUEST_SIZE_LIMIT_BYTES",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_REQUESTS_PER_MINUTE",
    "RATE_LIMIT_BURST",
    "RATE_LIMIT_EXEMPT_PATHS",
    "STORAGE_BACKEND",
    "DATABASE_URL",
    "REDIS_ENABLED",
    "REDIS_URL",
    "MCP_MODE",
    "MCP_SERVER_COMMAND_ALLOWLIST",
    "REAL_LLM_ACCEPTANCE_ENABLED",
    "REAL_LLM_MODEL",
    "REAL_LLM_API_KEY_ENV",
    "OIDC_ENABLED",
    "OIDC_ISSUER_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET_ENV",
    "OIDC_REDIRECT_URI",
    "OIDC_REQUIRE_HTTPS",
    "OIDC_DEFAULT_ROLE",
    "OIDC_ALLOWED_ROLES",
]

OIDC_RELATED = [
    "OIDC_ENABLED",
    "OIDC_ISSUER_URL",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET_ENV",
    "OIDC_REDIRECT_URI",
    "OIDC_SCOPES",
    "OIDC_ROLE_CLAIM",
    "OIDC_DEFAULT_ROLE",
    "OIDC_ALLOWED_ROLES",
    "OIDC_REQUIRE_HTTPS",
]

AUDIT_RELATED = [
    "AUDIT_RETENTION_ENABLED",
    "AUDIT_RETENTION_DAYS",
    "AUDIT_EXPORT_ENABLED",
    "AUDIT_EXPORT_MAX_ROWS",
    "AUDIT_EXPORT_FORMAT",
    "AUDIT_EXPORT_REDACTION_ENABLED",
]

REAL_LLM_RELATED = [
    "REAL_LLM_SMOKE_ENABLED",
    "REAL_LLM_ACCEPTANCE_ENABLED",
    "REAL_LLM_PREFLIGHT_ENABLED",
    "REAL_LLM_PREFLIGHT_NETWORK_CHECK",
    "REAL_LLM_MODEL",
    "REAL_LLM_API_KEY_ENV",
    "REAL_LLM_BASE_URL",
]

BOUNDARY_DECLARATIONS = [
    "read only drift check: no environment mutation",
    "no writing real secret values",
    "no user data deletion",
    "fake/offline default preserved",
    "no real external LLM execution",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _parse_env_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key = text.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def _settings_env_keys() -> set[str]:
    return {name.upper() for name in Settings.model_fields.keys()}


def _to_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve()))
    except Exception:
        return str(path)


def _presence(rows: list[str], *, example_keys: set[str], prod_keys: set[str], settings_keys: set[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key in rows:
        result.append(
            {
                "key": key,
                "in_env_example": key in example_keys,
                "in_env_production_example": key in prod_keys,
                "in_runtime_settings": key in settings_keys,
            }
        )
    return result


def _build_markdown(payload: dict[str, Any]) -> str:
    warnings = payload.get("warnings", [])
    lines = [
        "# Config Drift Check (Read Only)",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        "",
        "## Drift Summary",
        f"- missing_in_example: {len(payload.get('missing_in_example', []))}",
        f"- missing_in_production_example: {len(payload.get('missing_in_production_example', []))}",
        f"- warnings: {len(warnings)}",
        "",
        "## Compose Required Env",
    ]
    for item in payload.get("compose_required_env", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- {item.get('key', '')}: example={item.get('in_env_example', False)}, production_example={item.get('in_env_production_example', False)}"
        )

    lines.extend(
        [
            "",
            "## Boundary Declarations",
            "- read only drift check: no environment mutation",
            "- no writing real secret values",
            "- no user data deletion",
            "- fake/offline default preserved",
            "- no real external LLM execution",
            "",
        ]
    )

    if warnings:
        lines.append("## Warnings")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def build_config_drift_report(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    example_keys = _parse_env_keys(ENV_EXAMPLE_PATH)
    prod_keys = _parse_env_keys(ENV_PRODUCTION_EXAMPLE_PATH)
    settings_keys = _settings_env_keys()

    missing_in_example = sorted(prod_keys - example_keys)
    missing_in_production_example = sorted(example_keys - prod_keys)

    warnings: list[str] = []
    if missing_in_example:
        warnings.append("Some keys exist in .env.production.example but are missing in .env.example")
    if missing_in_production_example:
        warnings.append("Some keys exist in .env.example but are missing in .env.production.example")

    for key in COMPOSE_REQUIRED_ENV:
        if key not in prod_keys:
            warnings.append(f"compose required key missing in .env.production.example: {key}")

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "checked_files": [
            _to_rel(ENV_EXAMPLE_PATH),
            _to_rel(ENV_PRODUCTION_EXAMPLE_PATH),
            "app/core/config.py",
            "app/core/deployment_guard.py",
            "docker-compose.yml",
            "docker-compose.prod.yml",
        ],
        "missing_in_example": missing_in_example,
        "missing_in_production_example": missing_in_production_example,
        "deployment_guard_related": _presence(
            DEPLOYMENT_GUARD_RELATED,
            example_keys=example_keys,
            prod_keys=prod_keys,
            settings_keys=settings_keys,
        ),
        "oidc_related": _presence(
            OIDC_RELATED,
            example_keys=example_keys,
            prod_keys=prod_keys,
            settings_keys=settings_keys,
        ),
        "audit_related": _presence(
            AUDIT_RELATED,
            example_keys=example_keys,
            prod_keys=prod_keys,
            settings_keys=settings_keys,
        ),
        "real_llm_related": _presence(
            REAL_LLM_RELATED,
            example_keys=example_keys,
            prod_keys=prod_keys,
            settings_keys=settings_keys,
        ),
        "compose_required_env": _presence(
            COMPOSE_REQUIRED_ENV,
            example_keys=example_keys,
            prod_keys=prod_keys,
            settings_keys=settings_keys,
        ),
        "warnings": warnings,
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_config_drift"
    json_path = output_root / f"{stem}.json"
    markdown_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": "ok",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "warning_count": len(warnings),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build read-only config drift report (JSON + Markdown)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_config_drift_report(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
