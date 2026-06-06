from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_package"
DEFAULT_ACK_STATUS_DIR = ROOT_DIR / "docs" / "reports" / "manual_signoff_evidence_ack_status"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "manual_signoff_record.draft.json"

REQUIRED_ROLES = (
    ("release_manager", "确认发布窗口、回滚方案、变更审批和版本范围。"),
    ("security_reviewer", "确认密钥不泄漏、权限边界、审计证据和安全复核结论。"),
    ("business_owner", "确认业务只读/写入边界、试点范围和残余风险接受。"),
    ("operations_owner", "确认监控、备份恢复、值守和故障处置准备。"),
)
REQUIRED_ACKS = (
    "real_llm_preflight",
    "postgres_redis_mcp_smoke",
    "business_read_smoke",
    "closure_evidence_review",
)

SECRET_TEXT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"tp-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?|redis)://[^,\s]+"),
    re.compile(r"(?i)(api[_-]?key|token|client[_-]?secret|jwt[_-]?secret|password|secret)\s*[:=]\s*([^\s,]+)"),
]
SAFE_PLACEHOLDERS = {"secret-managed-token", "secret-managed-url", "set-in-local-env-only"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT_DIR), text=True, encoding="utf-8").strip()
    except Exception:
        return ""


def _contains_secret_like(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value)
    for pattern in SECRET_TEXT_PATTERNS:
        for match in pattern.finditer(text):
            if len(match.groups()) >= 2:
                candidate = str(match.group(2) or "").strip().strip("\"'<>").lower()
                if candidate in SAFE_PLACEHOLDERS:
                    continue
            return True
    return False


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return "[redacted-secret-like-text]" if _contains_secret_like(value) else value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {_redact(str(key)): _redact(item) for key, item in value.items()}
    return value


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    files = [item for item in directory.glob(pattern) if item.is_file()]
    if not files:
        return None

    def sort_key(item: Path) -> tuple[str, float, str]:
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        generated_at = str(payload.get("generated_at") or "") if isinstance(payload, dict) else ""
        return generated_at, item.stat().st_mtime, item.name

    return max(files, key=sort_key)


def _read_json(path: Path | None) -> tuple[dict[str, Any], list[str], str]:
    if path is None:
        return {}, ["manual_signoff_evidence_ack_status:not_found"], ""
    if not path.exists():
        return {}, ["manual_signoff_evidence_ack_status:not_found"], str(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, ["manual_signoff_evidence_ack_status:json_parse_failed"], str(path)
    if not isinstance(payload, dict):
        return {}, ["manual_signoff_evidence_ack_status:json_object_required"], str(path)
    return payload, [], str(path)


def _ack_items_from_status(payload: dict[str, Any]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item") or "")
        if item_id:
            by_id[item_id] = item

    output: list[dict[str, Any]] = []
    for item_id in REQUIRED_ACKS:
        source = by_id.get(item_id, {})
        output.append(
            {
                "item": item_id,
                "accepted": False,
                "recommended_accept": bool(source.get("recommended_accept", False)),
                "latest_report": _redact(str(source.get("latest_report") or "")),
                "source_status": _redact(str(source.get("source_status") or "missing")),
                "missing_conditions": _redact(
                    source.get("missing_conditions") if isinstance(source.get("missing_conditions"), list) else []
                ),
                "note": "人工复核该证据项后，将 accepted 改为 true；不得填写密钥、连接串或业务敏感数据。",
            }
        )
    return output


def build_manual_signoff_record_draft(
    *,
    output_path: str | Path | None = None,
    ack_status_report: str | Path | None = None,
) -> dict[str, Any]:
    target = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    ack_path = Path(ack_status_report) if ack_status_report else _latest_json(
        DEFAULT_ACK_STATUS_DIR,
        "*_manual_signoff_evidence_ack_status.json",
    )
    ack_payload, ack_errors, ack_path_text = _read_json(ack_path)
    generated_at = _utc_now_iso()
    commit = _run_git(["rev-parse", "HEAD"]) or "unknown"
    draft = {
        "generated_at": generated_at,
        "commit": commit,
        "manual_signoff_completed": False,
        "decision": "No-Go",
        "signed_at": "",
        "public_production_direct_launch": "No-Go",
        "auto_signed": False,
        "auto_approved": False,
        "auto_closed": False,
        "source_ack_status_report": _redact(ack_path_text),
        "source_ack_status": _redact(str(ack_payload.get("status") or "missing")) if ack_payload else "missing",
        "roles": [
            {
                "role": role,
                "name": "",
                "approved": False,
                "responsibility": responsibility,
            }
            for role, responsibility in REQUIRED_ROLES
        ],
        "evidence_acknowledgements": _ack_items_from_status(ack_payload),
        "notes": [
            "填写真实签核人姓名或工号；不要填写 token、API key、数据库连接串或客户敏感数据。",
            "只有人工确认受控试点可进入 Manual-Review 后，才可将 decision 改为 Go，并将四个 approved 改为 true。",
            "public_production_direct_launch 必须保持 No-Go。",
        ],
    }
    secret_like_detected = _contains_secret_like(draft) or _contains_secret_like(ack_payload)
    safe_draft = _redact(draft)
    target.write_text(json.dumps(safe_draft, ensure_ascii=False, indent=2), encoding="utf-8")
    status = "blocked" if secret_like_detected else ("partial" if ack_errors else "success")
    return {
        "status": status,
        "generated_at": generated_at,
        "output_path": str(target),
        "ack_status_report": _redact(ack_path_text),
        "missing_conditions": ack_errors + (["manual_signoff_record_draft:secret_like_output_detected"] if secret_like_detected else []),
        "manual_signoff_completed": False,
        "public_production_direct_launch": "No-Go",
        "secret_plaintext_output": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成待人工签署的生产落地签署记录草稿。")
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--ack-status-report", default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    summary = build_manual_signoff_record_draft(
        output_path=args.output_path,
        ack_status_report=args.ack_status_report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"output_path={summary['output_path']}")
    return 0 if summary["status"] in {"success", "partial", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
