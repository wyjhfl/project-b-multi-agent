from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "cross_tenant_audit_evidence"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]

REQUIRED_AUDIT_SCOPE_FIELDS = [
    "organization_id",
    "tenant_id",
    "project_id",
    "resource_id",
    "actor_principal_id",
    "decision",
    "denial_reason",
]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
]

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "cookie",
    "database_url",
    "jwt_secret",
    "password",
    "prompt",
    "query",
    "raw_prompt",
    "redis_url",
    "secret",
    "sql_prompt",
    "token",
    "user_query",
}

BOUNDARY_DECLARATIONS = [
    "只读跨租户审计与拒绝证据模板",
    "仅消费 JSON 元数据和文件存在性信息，不读取报告正文用于输出",
    "不修改 audit store schema",
    "不生成伪造的跨租户通过证据",
    "不启用 tenant enforcement",
    "不改 JWT payload",
    "不写业务数据",
    "不修改 .env 或环境变量",
    "不读取或输出 prompt 原文、secret 原文、token 原文或连接串密码原文",
    "不执行真实外网 LLM",
    "不连接真实外部 IdP",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不宣称公网生产可直接上线",
    "不宣称真实 LLM 生产验收完成",
    "不宣称生产级 SSO/OIDC 或多租户完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _sanitize_text(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _contains_secret_like_text(value: Any) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in SECRET_TEXT_PATTERNS)


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in SENSITIVE_KEYS:
                return True
            if _contains_sensitive_key(nested):
                return True
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_bool(value: Any) -> bool:
    return bool(value) if isinstance(value, bool) else False


def _load_json_source(name: str, path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "name": name,
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:input_not_provided"],
            "warnings": [],
            "secret_detected": False,
        }

    path = Path(path_value)
    if not path.exists():
        return {
            "name": name,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:path_not_found"],
            "warnings": [],
            "secret_detected": False,
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "name": name,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {"suffix": path.suffix.lower(), "size_bytes": path.stat().st_size},
            "missing_conditions": [f"{name}:json_file_required"],
            "warnings": [],
            "secret_detected": False,
        }

    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except Exception as exc:
        return {
            "name": name,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {"suffix": path.suffix.lower(), "size_bytes": path.stat().st_size},
            "missing_conditions": [f"{name}:json_parse_failed"],
            "warnings": [f"{name}:json_parse_failed:{type(exc).__name__}"],
            "secret_detected": False,
        }

    if not isinstance(payload, dict) or not payload:
        return {
            "name": name,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "metadata": {"suffix": path.suffix.lower(), "size_bytes": path.stat().st_size},
            "missing_conditions": [f"{name}:json_empty_or_not_object"],
            "warnings": [],
            "secret_detected": False,
        }

    secret_detected = _contains_secret_like_text(raw_text) or _contains_sensitive_key(payload)
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]
    status = str(payload.get("status") or payload.get("readiness_status") or "partial").strip()
    if status == "ready":
        status = "success"
    if status not in STATUS_VOCABULARY:
        status = "partial"
    if secret_detected:
        status = "blocked"
        missing_conditions.append(f"{name}:sensitive_plaintext_detected")
        warnings.append(f"{name}:sensitive_plaintext_detected")

    metadata = {
        "version": _sanitize_text(payload.get("version", "")),
        "phase": _sanitize_text(payload.get("phase", "")),
        "status": status,
        "read_only": _safe_bool(payload.get("read_only")),
        "real_llm_executed": _safe_bool(payload.get("real_llm_executed")),
        "real_idp_connected": _safe_bool(payload.get("real_idp_connected")),
        "tenant_enforcement_enabled": _safe_bool(payload.get("tenant_enforcement_enabled")),
        "permission_count": int(payload.get("permission_count", 0) or 0),
        "denied_pair_count": int(payload.get("denied_pair_count", 0) or 0),
        "scenario_count": int(payload.get("scenario_count", 0) or 0),
        "source_keys": sorted(str(key) for key in payload.keys()),
    }

    if metadata["real_llm_executed"]:
        missing_conditions.append(f"{name}:real_llm_executed_unexpected")
    if metadata["real_idp_connected"]:
        missing_conditions.append(f"{name}:real_idp_connected_unexpected")
    if metadata["tenant_enforcement_enabled"]:
        missing_conditions.append(f"{name}:tenant_enforcement_enabled_unexpected")

    return {
        "name": name,
        "path": _sanitize_text(path),
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "metadata": metadata,
        "missing_conditions": sorted(set(missing_conditions)),
        "warnings": sorted(set(warnings)),
        "secret_detected": secret_detected,
    }


def _load_doc_source(name: str, path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "name": name,
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:input_not_provided"],
            "warnings": [],
            "secret_detected": False,
        }

    path = Path(path_value)
    if not path.exists():
        return {
            "name": name,
            "path": _sanitize_text(path),
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "metadata": {},
            "missing_conditions": [f"{name}:path_not_found"],
            "warnings": [],
            "secret_detected": False,
        }

    return {
        "name": name,
        "path": _sanitize_text(path),
        "provided": True,
        "exists": True,
        "loaded": False,
        "status": "partial",
        "metadata": {
            "suffix": path.suffix.lower(),
            "size_bytes": path.stat().st_size if path.is_file() else 0,
            "content_read_for_output": False,
        },
        "missing_conditions": [],
        "warnings": [],
        "secret_detected": False,
    }


def _evidence_templates() -> list[dict[str, Any]]:
    return [
        {
            "template_id": "allow_evidence",
            "purpose": "记录同租户或授权 scope 内允许访问的证据要求",
            "required_fields": [
                "actor_principal_id",
                "role",
                "permission",
                "organization_id",
                "tenant_id",
                "project_id",
                "resource_id",
                "decision=allow",
                "policy_version",
            ],
            "current_status": "template_only",
        },
        {
            "template_id": "deny_evidence",
            "purpose": "记录跨租户、跨项目或权限不足时的拒绝证据要求",
            "required_fields": REQUIRED_AUDIT_SCOPE_FIELDS + ["permission", "role", "policy_version"],
            "expected_http_status": [401, 403],
            "current_status": "template_only",
        },
        {
            "template_id": "audit_record_evidence",
            "purpose": "定义未来 audit event 必须携带的 tenant/org/project/resource scope 字段",
            "required_fields": REQUIRED_AUDIT_SCOPE_FIELDS + ["event_id", "event_type", "timestamp", "outcome"],
            "current_status": "template_only",
        },
        {
            "template_id": "export_redaction_evidence",
            "purpose": "验证审计导出只输出白名单字段和脱敏 detail",
            "required_fields": ["export_id", "field_whitelist", "detail_redacted", "prompt_plaintext_output=false", "secret_plaintext_output=false"],
            "current_status": "partially_supported_by_existing_audit_export",
        },
        {
            "template_id": "reviewer_owner_evidence",
            "purpose": "记录拒绝、例外和复核责任人，支持后续治理闭环",
            "required_fields": ["owner", "reviewer", "review_reason", "reviewed_at", "expires_at", "compensating_controls"],
            "current_status": "template_only",
        },
    ]


def _denial_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "cross_tenant_resource_read_denied",
            "condition": "actor.tenant_id != resource.tenant_id",
            "expected_decision": "deny",
            "expected_http_status": 403,
            "required_audit_fields": REQUIRED_AUDIT_SCOPE_FIELDS,
            "current_status": "future_enforcement_required",
        },
        {
            "case_id": "cross_project_resource_write_denied",
            "condition": "actor.project_id not in resource.allowed_project_ids",
            "expected_decision": "deny",
            "expected_http_status": 403,
            "required_audit_fields": REQUIRED_AUDIT_SCOPE_FIELDS,
            "current_status": "future_enforcement_required",
        },
        {
            "case_id": "missing_scope_claim_denied",
            "condition": "JWT 或服务端 principal 缺少 tenant/org/project scope",
            "expected_decision": "deny",
            "expected_http_status": 403,
            "required_audit_fields": ["actor_principal_id", "decision", "denial_reason"],
            "current_status": "future_enforcement_required",
        },
        {
            "case_id": "audit_export_redaction_required",
            "condition": "audit export 请求必须启用 redaction 且只输出白名单字段",
            "expected_decision": "deny_when_redaction_disabled",
            "expected_http_status": 403,
            "required_audit_fields": ["actor_principal_id", "decision", "denial_reason"],
            "current_status": "supported_by_existing_audit_export_guard",
        },
    ]


def _redaction_boundaries() -> list[dict[str, Any]]:
    return [
        {
            "boundary_id": "prompt_plaintext",
            "must_not_output": ["prompt", "raw_prompt", "sql_prompt", "user_query", "query"],
            "expected_marker": "[REDACTED_PROMPT]",
        },
        {
            "boundary_id": "secret_plaintext",
            "must_not_output": ["api_key", "token", "authorization", "cookie", "password", "secret", "client_secret", "jwt_secret"],
            "expected_marker": "[REDACTED]",
        },
        {
            "boundary_id": "connection_string_password",
            "must_not_output": ["DATABASE_URL password", "REDIS_URL password"],
            "expected_marker": "[REDACTED]",
        },
    ]


def _derive_status(sources: list[dict[str, Any]], missing_conditions: list[str]) -> str:
    if any(source.get("secret_detected") for source in sources):
        return "blocked"
    if not any(source.get("provided") for source in sources):
        return "partial"
    if missing_conditions:
        return "partial"
    return "partial"


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.6 Phase 16.5 跨租户审计与拒绝证据模板",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- status: {payload.get('status', '')}",
        f"- read_only: {payload.get('read_only', True)}",
        f"- tenant_enforcement_enabled: {payload.get('tenant_enforcement_enabled', False)}",
        f"- audit_store_schema_changed: {payload.get('audit_store_schema_changed', False)}",
        "",
        "## 必需 audit scope 字段",
    ]
    for field in payload.get("required_audit_scope_fields", []):
        lines.append(f"- {field}")

    lines.extend(["", "## 证据模板"])
    for template in payload.get("evidence_templates", []):
        lines.append(f"- {template['template_id']}: {template['current_status']}")

    lines.extend(["", "## 拒绝用例"])
    for case in payload.get("denial_cases", []):
        lines.append(f"- {case['case_id']}: {case['expected_decision']} / {case['current_status']}")

    lines.extend(["", "## 缺失条件"])
    for item in payload.get("missing_conditions", []):
        lines.append(f"- {item}")

    lines.extend(["", "## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_cross_tenant_audit_evidence(
    *,
    output_dir: str | Path | None = None,
    rbac_matrix: str | Path | None = None,
    tenant_model_doc: str | Path | None = None,
    audit_export_sample: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    sources = [
        _load_json_source("rbac_matrix", rbac_matrix),
        _load_doc_source("tenant_model_doc", tenant_model_doc),
        _load_json_source("audit_export_sample", audit_export_sample),
    ]
    missing_conditions = sorted(
        {
            item
            for source in sources
            for item in source.get("missing_conditions", [])
        }
        | {
            "tenant_enforcement:not_enabled",
            "audit_store_schema:not_changed",
            "runtime_cross_tenant_denial_tests:not_implemented",
        }
    )
    warnings = sorted({item for source in sources for item in source.get("warnings", [])})
    status = _derive_status(sources, missing_conditions)

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "phase": "v3.6 Phase 16.5",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "real_idp_connected": False,
        "tenant_enforcement_enabled": False,
        "audit_store_schema_changed": False,
        "business_data_written": False,
        "secret_plaintext_output": False,
        "prompt_plaintext_output": False,
        "jwt_payload_changed": False,
        "sources": sources,
        "evidence_templates": _evidence_templates(),
        "required_audit_scope_fields": REQUIRED_AUDIT_SCOPE_FIELDS,
        "denial_cases": _denial_cases(),
        "redaction_boundaries": _redaction_boundaries(),
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "recommended_actions": [
            "后续接入 tenant enforcement 前，先把 audit event scope 字段纳入 schema 迁移设计。",
            "跨租户 allow/deny 证据必须来自真实运行时拒绝链路，不得用模板伪造通过。",
            "审计导出继续保持字段白名单和 detail 脱敏，不导出 prompt 原文或 secret 原文。",
            "Phase 16.6 release prep 仅做发布材料收口，是否打 tag 需单独确认。",
        ],
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_cross_tenant_audit_evidence"
    json_path = output_root / f"{stem}.json"
    md_path = output_root / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return {
        "status": status,
        "generated_at": generated_at,
        "commit": commit,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "real_idp_connected": False,
        "tenant_enforcement_enabled": False,
        "audit_store_schema_changed": False,
        "secret_plaintext_output": False,
        "prompt_plaintext_output": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "missing_count": len(missing_conditions),
        "source_count": len(sources),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.6 跨租户审计与拒绝证据模板（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--rbac-matrix", default=None)
    parser.add_argument("--tenant-model-doc", default=None)
    parser.add_argument("--audit-export-sample", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_cross_tenant_audit_evidence(
        output_dir=args.output_dir,
        rbac_matrix=args.rbac_matrix,
        tenant_model_doc=args.tenant_model_doc,
        audit_export_sample=args.audit_export_sample,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
