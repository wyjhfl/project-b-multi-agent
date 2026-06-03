from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "pilot_handoff"

BOUNDARY_DECLARATIONS = [
    "企业内网试点可继续",
    "公网直上 No-Go",
    "真实生产验收需另行执行",
    "默认 fake/offline",
    "默认 pytest/CI 不调用真实 LLM",
    "不执行真实外网 LLM",
    "不读取或输出真实 secret 原文",
    "不宣称生产级 SSO/OIDC 完成",
    "不宣称多租户或复杂 BI 全量完成",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        output = subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8")
        return output.strip()
    except Exception:
        return ""


def _exists(path: str) -> bool:
    return (ROOT_DIR / path).exists()


def _build_roles() -> list[dict[str, Any]]:
    return [
        {"role": "admin", "scope": "配置预检、演练窗口确认、审批策略复核", "rbac_boundary": "默认 RBAC_ENABLED=false；企业试点需显式启用"},
        {"role": "operator", "scope": "日常 /operations 查看、故障演练、证据归档", "rbac_boundary": "只读优先，不绕过后端审批链路"},
        {"role": "viewer", "scope": "查看只读摘要、报告和 handoff 证据", "rbac_boundary": "不得执行写入型工具动作"},
        {"role": "auditor", "scope": "审计导出、脱敏边界和 release/tag 记录复核", "rbac_boundary": "审计导出默认脱敏"},
    ]


def _build_handoff_items() -> list[dict[str, Any]]:
    items = [
        {
            "item": "RBAC 边界",
            "status": "ready",
            "evidence_paths": ["app/auth/dependencies.py", "docs/production_readiness_checklist.md"],
            "note": "auth_enabled/rbac_enabled 默认 false；企业试点设置 AUTH_ENABLED=true + RBAC_ENABLED=true。",
        },
        {
            "item": "OIDC 最小演练边界",
            "status": "ready" if _exists("docs/oidc_minimal_idp_drill_v31.md") else "skipped",
            "evidence_paths": ["docs/oidc_minimal_idp_drill_v31.md"],
            "note": "最小 IdP 配置演练，不等于生产级 SSO/OIDC 完成。",
        },
        {
            "item": "real LLM opt-in skipped/ready 解释",
            "status": "ready" if _exists("docs/optional_integration_readiness_matrix_v34.md") else "skipped",
            "evidence_paths": ["docs/optional_integration_readiness_matrix_v34.md", "docs/real_llm_optional_retry_log_v32.md"],
            "note": "缺少 opt-in 条件必须 skipped；真实 LLM smoke 不等于生产验收。",
        },
        {
            "item": "incident rehearsal 结果引用",
            "status": "ready" if _exists("docs/incident_rehearsal_pack_v34.md") else "skipped",
            "evidence_paths": ["docs/incident_rehearsal_pack_v34.md"],
            "note": "只读演练包覆盖 skipped/blocked/partial 状态解释。",
        },
        {
            "item": "evidence archive manifest 引用",
            "status": "ready" if _exists("docs/evidence_archive_manifest_v34.md") else "skipped",
            "evidence_paths": ["docs/evidence_archive_manifest_v34.md"],
            "note": "只读索引证据，不删除文件，不自动清理。",
        },
        {
            "item": "optional integration readiness 引用",
            "status": "ready" if _exists("docs/optional_integration_readiness_matrix_v34.md") else "skipped",
            "evidence_paths": ["docs/optional_integration_readiness_matrix_v34.md"],
            "note": "仅检查配置存在性和本地条件，不执行真实集成。",
        },
        {
            "item": "backup/restore/checklist 链接",
            "status": "ready" if _exists("docs/backup_restore_checklist_v31.md") else "skipped",
            "evidence_paths": ["docs/backup_restore_checklist_v31.md", "docs/operations_troubleshooting_index_v31.md"],
            "note": "文档化排障与备份恢复，不删除用户数据。",
        },
    ]
    return items


def _build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v3.4 企业内网试点交接清单（只读）",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- status: {payload.get('status', '')}",
        f"- go_no_go: {payload.get('go_no_go', {}).get('summary', '')}",
        "",
        "## 角色",
    ]
    for role in payload.get("roles", []):
        lines.extend([f"### {role.get('role', '')}", f"- scope: {role.get('scope', '')}", f"- rbac_boundary: {role.get('rbac_boundary', '')}", ""])
    lines.append("## 交接项")
    for item in payload.get("handoff_items", []):
        lines.extend([f"### {item.get('item', '')}", f"- status: {item.get('status', '')}", f"- note: {item.get('note', '')}", ""])
    lines.append("## 边界声明")
    for item in payload.get("boundary_declarations", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_pilot_handoff_checklist(*, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_root = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    output_root.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    short_commit = commit[:8] if commit != "unknown" else "unknown"
    handoff_items = _build_handoff_items()
    missing_items = [item["item"] for item in handoff_items if item["status"] != "ready"]
    status = "ready" if not missing_items else "partial"

    payload = {
        "generated_at": generated_at,
        "commit": commit,
        "version": "3.6.0",
        "status": status,
        "mode": "fake_offline_default",
        "read_only": True,
        "real_llm_executed": False,
        "roles": _build_roles(),
        "handoff_items": handoff_items,
        "missing_items": missing_items,
        "known_limitations": [
            "不宣称公网生产可直接上线。",
            "不宣称真实 LLM 生产验收已完成。",
            "不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。",
            "真实外部 MCP、生产级 SSO/OIDC、多租户和复杂 BI 仍需后续专项验收。",
        ],
        "go_no_go": {
            "intranet_pilot": "Go",
            "public_production_direct_launch": "No-Go",
            "summary": "企业内网试点可继续；公网直上 No-Go；真实生产验收需另行执行。",
        },
        "boundary_declarations": BOUNDARY_DECLARATIONS,
    }

    stem = f"{generated_at.replace(':', '-').replace('+', '_')}_{short_commit}_pilot_handoff_checklist"
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
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "output_dir": str(output_root),
        "missing_items": missing_items,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 v3.4 企业内网试点交接清单（JSON + Markdown）")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_pilot_handoff_checklist(output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_path={summary['json_path']}")
    print(f"markdown_path={summary['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
