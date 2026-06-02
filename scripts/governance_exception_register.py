from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "governance_exceptions"

STATUS_VOCABULARY = ["success", "skipped", "blocked", "partial", "failed"]
EXCEPTION_STATUS_VOCABULARY = ["pending_review", "skipped", "blocked", "expired", "closed"]

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)=([^,\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?|redis)://[^,\s]+"),
]

BOUNDARY_DECLARATIONS = [
    "只读治理例外登记册",
    "仅消费 JSON 摘要和安全元数据，不读取报告正文",
    "不自动批准例外",
    "不绕过 deployment guard、安全响应头、审计脱敏或审批链路",
    "不写业务数据",
    "不修改 .env 或环境变量",
    "不调用真实外网 LLM",
    "不连接真实外部 MCP",
    "默认 fake/offline，默认 pytest/CI 不调用真实 LLM",
    "不读取或输出真实 secret 原文",
    "不移动、删除、重建历史 tag",
    "不宣称公网生产可直接上线",
    "不宣称真实 LLM 生产验收完成",
    "不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成",
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


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_status(value: Any) -> str:
    raw = str(value or "").strip()
    if raw == "ready":
        return "success"
    if raw in STATUS_VOCABULARY:
        return raw
    if raw:
        return "partial"
    return "skipped"


def _source_specs(
    *,
    config_drift: str | Path | None,
    governance_policy: str | Path | None,
    incident_report: str | Path | None,
    operator_scoring: str | Path | None,
    controlled_integration: str | Path | None,
) -> list[tuple[str, str, str | Path | None]]:
    return [
        ("config_drift", "config", config_drift),
        ("governance_policy", "governance", governance_policy),
        ("incident_report", "operations", incident_report),
        ("operator_scoring", "operations", operator_scoring),
        ("controlled_integration", "integration", controlled_integration),
    ]


def _load_source(name: str, scope: str, path_value: str | Path | None) -> dict[str, Any]:
    if not path_value:
        return {
            "name": name,
            "scope": scope,
            "path": "",
            "provided": False,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:input_not_provided"],
            "warnings": [],
            "recommended_actions": [],
            "secret_detected": False,
            "metadata": {},
        }

    path = Path(path_value)
    if not path.exists():
        return {
            "name": name,
            "scope": scope,
            "path": str(path),
            "provided": True,
            "exists": False,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:path_not_found"],
            "warnings": [],
            "recommended_actions": [],
            "secret_detected": False,
            "metadata": {},
        }
    if not path.is_file() or path.suffix.lower() != ".json":
        return {
            "name": name,
            "scope": scope,
            "path": str(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:json_file_required"],
            "warnings": [],
            "recommended_actions": [],
            "secret_detected": False,
            "metadata": {},
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "name": name,
            "scope": scope,
            "path": str(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:json_parse_failed"],
            "warnings": [f"{name}:json_parse_failed:{type(exc).__name__}"],
            "recommended_actions": [],
            "secret_detected": False,
            "metadata": {},
        }
    if not isinstance(payload, dict) or not payload:
        return {
            "name": name,
            "scope": scope,
            "path": str(path),
            "provided": True,
            "exists": True,
            "loaded": False,
            "status": "skipped",
            "missing_conditions": [f"{name}:json_empty_or_not_object"],
            "warnings": [],
            "recommended_actions": [],
            "secret_detected": False,
            "metadata": {},
        }

    secret_detected = _contains_secret_like_text(json.dumps(payload, ensure_ascii=False))
    missing_conditions = [_sanitize_text(item) for item in _safe_list(payload.get("missing_conditions"))]
    warnings = [_sanitize_text(item) for item in _safe_list(payload.get("warnings"))]
    skipped_reasons = [_sanitize_text(item) for item in _safe_list(payload.get("skipped_reasons"))]
    recommended_actions = [_sanitize_text(item) for item in _safe_list(payload.get("recommended_actions"))]
    status = _normalize_status(payload.get("status") or payload.get("readiness_status"))

    if status == "skipped":
        missing_conditions.append(f"{name}:source_status_skipped")
    if bool(payload.get("real_llm_executed", False)):
        missing_conditions.append(f"{name}:real_llm_executed_unexpected")
    if bool(payload.get("external_mcp_connected", False)):
        missing_conditions.append(f"{name}:external_mcp_connected_unexpected")
    if bool(payload.get("auto_approved", False)):
        missing_conditions.append(f"{name}:auto_approved_unexpected")
    if payload.get("read_only") is False:
        missing_conditions.append(f"{name}:not_read_only")
    if secret_detected:
        missing_conditions.append(f"{name}:secret_like_value_detected")
        warnings.append(f"{name}:secret_like_value_detected")

    metadata = {
        "version": _sanitize_text(payload.get("version", "")),
        "mode": _sanitize_text(payload.get("mode", "")),
        "status": status,
        "read_only": bool(payload.get("read_only", False)),
        "real_llm_executed": bool(payload.get("real_llm_executed", False)),
        "external_mcp_connected": bool(payload.get("external_mcp_connected", False)),
        "missing_condition_count": len(missing_conditions),
        "warning_count": len(warnings),
        "recommended_action_count": len(recommended_actions),
    }

    return {
        "name": name,
        "scope": scope,
        "path": str(path),
        "provided": True,
        "exists": True,
        "loaded": True,
        "status": status,
        "missing_conditions": missing_conditions + skipped_reasons,
        "warnings": warnings,
        "recommended_actions": recommended_actions,
        "secret_detected": secret_detected,
        "metadata": metadata,
    }


def _exception_status(source: dict[str, Any]) -> str:
    conditions = source.get("missing_conditions", [])
    if source.get("secret_detected") or any(
        marker in condition
        for condition in conditions
        for marker in ["real_llm_executed_unexpected", "external_mcp_connected_unexpected", "auto_approved_unexpected", "not_read_only"]
    ):
        return "blocked"
    if not source.get("loaded"):
        return "skipped"
    return "pending_review"


def _build_exception(source: dict[str, Any], index: int) -> dict[str, Any]:
    status = _exception_status(source)
    condition_preview = source.get("missing_conditions") or source.get("warnings") or [f"{source['name']}:manual_review_required"]
    risk = "; ".join(_sanitize_text(item) for item in condition_preview[:5])
    if len(condition_preview) > 5:
        risk += "; ..."
    return {
        "exception_id": f"v35-15-4-{index:03d}",
        "source": source["name"],
        "risk_description": risk,
        "scope": source["scope"],
        "owner": "manual_owner_required",
        "expires_at": "manual_expiry_required",
        "compensating_controls": [
            "保留默认 fake/offline 路径",
            "保持审批链路、审计脱敏和 deployment guard 边界",
            "在人工评审前不得启用真实外部集成",
        ],
        "review_evidence": {
            "path": _sanitize_text(source.get("path", "")),
            "fields": ["status", "missing_conditions", "warnings", "recommended_actions"],
        },
        "status": status,
        "approval_state": "not_approved",
        "next_actions": _next_actions_for_exception(status, source),
    }


def _next_actions_for_exception(status: str, source: dict[str, Any]) -> list[str]:
    if status == "blocked":
        return ["先关闭 secret、只读边界或真实外部执行风险，再进入人工例外评审。"]
    if status == "skipped":
        return ["补充来源 JSON 摘要后重新生成治理例外登记册。"]
    actions = ["由人工补充责任人、到期时间、补偿控制和复核证据。"]
    actions.extend(source.get("recommended_actions", [])[:3])
    return [_sanitize_text(item) for item in actions]


def _derive_status(sources: list[dict[str, Any]], exceptions: list[dict[str, Any]]) -> str:
    if any(item.get("status") == "blocked" for item in exceptions):
        return "blocked"
    loaded_count = sum(1 for item in sources if item.get("loaded"))
    if loaded_count == 0:
        return "skipped"
    if any(item.get("status") == "skipped" for item in exceptions):
        return "partial"
    return "success"


def _recommended_actions(status: str, exceptions: list[dict[str, Any]]) -> list[str]:
    actions = [
        "登记册仅用于人工治理复核，不自动批准例外。",
        "补齐 owner、expires_at、compensating_controls 和 review_evidence 后再进入人工审批。",
        "保持默认 fake/offline，未显式 opt-in 时不要执行真实外网 LLM。",
    ]
    if status == "skipped":
        actions.append("补充 config drift、governance policy、incident、operator scoring 或 controlled integration JSON 输入后重新生成。")
    if status == "blocked":
        actions.append("优先处理 blocked 例外，尤其是 secret 原文、not_read_only、真实 LLM 或真实 MCP 执行风险。")
    if any(item.get("status") == "pending_review" for item in exceptions):
        actions.append("pending_review 条目必须由人工判断是否接受、拒绝或关闭。")
    return sorted(set(actions))


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.5 治理例外登记册（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- version: {payload.get('version', '')}",
        f"- mode: {payload.get('mode', '')}",
        f"- status: {payload.get('status', '')}",
        f"- auto_approved: {payload.get('auto_approved', False)}",
        "",
        "## 例外候选项",
    ]
    exceptions = payload.get("exception_register", [])
    if not exceptions:
        lines.append("- none")
    for item in exceptions:
        lines.extend(
            [
                f"### {item.get('exception_id', '')}",
                f"- source: {item.get('source', '')}",
                f"- scope: {item.get('scope', '')}",
                f"- status: {item.get('status', '')}",
                f"- approval_state: {item.get('approval_state', '')}",
                f"- risk_description: {item.get('risk_description', '')}",
                f"- owner: {item.get('owner', '')}",
                f"- expires_at: {item.get('expires_at', '')}",
                "",
            ]
        )
    lines.extend(["## 建议动作"])
    for item in payload.get("recommended_actions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## 边界声明"])
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_governance_exception_register(
    *,
    output_dir: str | Path | None = None,
    config_drift: str | Path | None = None,
    governance_policy: str | Path | None = None,
    incident_report: str | Path | None = None,
    operator_scoring: str | Path | None = None,
    controlled_integration: str | Path | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"

    sources = [
        _load_source(name, scope, path)
        for name, scope, path in _source_specs(
            config_drift=config_drift,
            governance_policy=governance_policy,
            incident_report=incident_report,
            operator_scoring=operator_scoring,
            controlled_integration=controlled_integration,
        )
    ]
    exceptions = [_build_exception(source, index + 1) for index, source in enumerate(sources)]
    status = _derive_status(sources, exceptions)
    missing_conditions = sorted({item for source in sources for item in source.get("missing_conditions", [])})
    warnings = sorted({item for source in sources for item in source.get("warnings", [])})

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.5.0",
        "mode": "fake_offline_default",
        "status": status,
        "status_vocabulary": STATUS_VOCABULARY,
        "exception_status_vocabulary": EXCEPTION_STATUS_VOCABULARY,
        "read_only": True,
        "real_llm_executed": False,
        "external_mcp_connected": False,
        "service_started": False,
        "auto_approved": False,
        "input_sources": sources,
        "exception_register": exceptions,
        "exception_count": len(exceptions),
        "missing_conditions": missing_conditions,
        "warnings": warnings,
        "recommended_actions": _recommended_actions(status, exceptions),
        "boundary_declarations": BOUNDARY_DECLARATIONS,
        "output_dir": str(output_root),
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_governance_exception_register"
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
        "external_mcp_connected": False,
        "service_started": False,
        "auto_approved": False,
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "exception_count": len(exceptions),
        "missing_conditions": missing_conditions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.5 治理例外登记册（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--config-drift", default=None)
    parser.add_argument("--governance-policy", default=None)
    parser.add_argument("--incident-report", default=None)
    parser.add_argument("--operator-scoring", default=None)
    parser.add_argument("--controlled-integration", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_governance_exception_register(
        output_dir=args.output_dir,
        config_drift=args.config_drift,
        governance_policy=args.governance_policy,
        incident_report=args.incident_report,
        operator_scoring=args.operator_scoring,
        controlled_integration=args.controlled_integration,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
