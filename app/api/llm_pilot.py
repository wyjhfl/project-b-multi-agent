from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from app.auth.dependencies import require_permission
from app.harness.llm.pilot_report import DEFAULT_PILOT_REPORT_DIR, sanitize_pilot_report_payload

router = APIRouter(prefix="/llm/pilot", tags=["llm_pilot"])

_REPORT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_MARKDOWN_BOUNDARY_HEADER = "## 边界声明"
_MARKDOWN_BOUNDARY_LINE_1 = "- 只读查看，不会触发真实 LLM 调用。"
_MARKDOWN_BOUNDARY_LINE_2 = "- 内容已脱敏，不包含 prompt 原文与密钥原文。"


def _get_report_dir() -> Path:
    override = (os.getenv("REAL_LLM_PILOT_REPORT_DIR", "") or "").strip()
    if override:
        return Path(override)
    return DEFAULT_PILOT_REPORT_DIR


def _validate_report_id(report_id: str) -> str:
    rid = (report_id or "").strip()
    if not _REPORT_ID_PATTERN.fullmatch(rid) or rid in {".", ".."} or ".." in rid:
        raise HTTPException(status_code=400, detail={"error": "invalid_report_id"})
    return rid


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return sanitize_pilot_report_payload(payload)


def _build_markdown_preview(payload: dict[str, Any]) -> str:
    evidence_links = payload.get("evidence_links") or {}
    lines = [
        "# Pilot Evidence Report (Read Only)",
        "",
        f"- report_id: {payload.get('report_id', '')}",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- provider/model: {payload.get('provider', '')} / {payload.get('model', '')}",
        f"- scenario: {payload.get('scenario', '')}",
        f"- outcome: {payload.get('outcome', '')}",
        f"- request_id: {payload.get('request_id', '')}",
        f"- fallback_used: {payload.get('fallback_used', False)}",
        f"- cost: {payload.get('cost', 0)}",
        f"- tokens(prompt/completion/total): {payload.get('prompt_tokens', 0)}/{payload.get('completion_tokens', 0)}/{payload.get('total_tokens', 0)}",
        f"- audit_event_id: {evidence_links.get('audit_event_id', '')}",
        f"- audit_event_type: {evidence_links.get('audit_event_type', '')}",
        "",
        _MARKDOWN_BOUNDARY_HEADER,
        _MARKDOWN_BOUNDARY_LINE_1,
        _MARKDOWN_BOUNDARY_LINE_2,
    ]
    return "\n".join(lines)


def _find_report_json_file(report_id: str) -> Path | None:
    report_dir = _get_report_dir()
    if not report_dir.exists() or not report_dir.is_dir():
        return None

    matched: list[Path] = []
    for file_path in report_dir.iterdir():
        if not file_path.is_file() or file_path.suffix.lower() != ".json":
            continue
        payload = _load_json(file_path)
        if not payload:
            continue
        if str(payload.get("report_id") or "") == report_id:
            matched.append(file_path)

    if not matched:
        return None
    matched.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matched[0]


@router.get("/reports")
async def list_pilot_reports(_current_user=Depends(require_permission("audit:read"))):
    report_dir = _get_report_dir()
    if not report_dir.exists() or not report_dir.is_dir():
        return []

    items: list[dict[str, Any]] = []
    for file_path in sorted(report_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not file_path.is_file() or file_path.suffix.lower() != ".json":
            continue
        payload = _load_json(file_path)
        if not payload:
            continue

        evidence_links = payload.get("evidence_links") or {}
        if not evidence_links and payload.get("cases"):
            first_case = payload["cases"][0] if isinstance(payload["cases"], list) and payload["cases"] else {}
            if isinstance(first_case, dict):
                evidence_links = first_case.get("evidence_links") or {}

        items.append(
            {
                "report_id": payload.get("report_id") or file_path.stem,
                "generated_at": payload.get("generated_at", ""),
                "provider": payload.get("provider", ""),
                "model": payload.get("model", ""),
                "scenario": payload.get("scenario", ""),
                "outcome": payload.get("outcome", ""),
                "request_id": payload.get("request_id", ""),
                "real_call_succeeded": bool(payload.get("real_call_succeeded", False)),
                "fallback_used": bool(payload.get("fallback_used", False)),
                "cost": float(payload.get("cost", 0.0) or 0.0),
                "prompt_tokens": int(payload.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(payload.get("completion_tokens", 0) or 0),
                "total_tokens": int(payload.get("total_tokens", 0) or 0),
                "audit_event_id": str(evidence_links.get("audit_event_id") or ""),
                "audit_event_type": str(evidence_links.get("audit_event_type") or ""),
                "path": file_path.name,
                "name": file_path.name,
            }
        )
    return items


@router.get("/reports/{report_id}")
async def get_pilot_report(report_id: str, _current_user=Depends(require_permission("audit:read"))):
    rid = _validate_report_id(report_id)
    file_path = _find_report_json_file(rid)
    if file_path is None:
        raise HTTPException(status_code=404, detail={"error": "pilot_report_not_found", "report_id": rid})
    payload = _load_json(file_path)
    if not payload:
        raise HTTPException(status_code=404, detail={"error": "pilot_report_not_found", "report_id": rid})
    payload["name"] = file_path.name
    return payload


@router.get("/reports/{report_id}/markdown")
async def get_pilot_report_markdown(report_id: str, _current_user=Depends(require_permission("audit:read"))):
    rid = _validate_report_id(report_id)
    file_path = _find_report_json_file(rid)
    if file_path is None:
        raise HTTPException(status_code=404, detail={"error": "pilot_report_not_found", "report_id": rid})
    payload = _load_json(file_path)
    if not payload:
        raise HTTPException(status_code=404, detail={"error": "pilot_report_not_found", "report_id": rid})
    return PlainTextResponse(content=_build_markdown_preview(payload), media_type="text/markdown; charset=utf-8")
