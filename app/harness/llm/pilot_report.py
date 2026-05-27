from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core.structured_logging import redact_sensitive_value

DEFAULT_PILOT_REPORT_DIR = Path("docs/reports/real_llm_pilot")
REDACTED_PROMPT_PLACEHOLDER = "[REDACTED_PROMPT]"

SENSITIVE_KEYS_EXACT = {
    "token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "authorization",
    "cookie",
    "jwt",
    "database_url",
    "redis_url",
    "key",
}
SENSITIVE_KEY_PATTERNS = (
    "token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "authorization",
    "cookie",
    "jwt",
    "database_url",
    "redis_url",
    "key",
)
PROMPT_FIELD_PATTERNS = (
    "prompt",
    "query",
    "user_query",
    "raw_prompt",
    "sql_prompt",
    "input",
    "messages",
)
PILOT_EVIDENCE_SAFE_KEYS = {
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "api_key_present",
    "cache_hit",
    "budget_action",
    "latency_ms",
    "cost",
    "request_id",
    "provider",
    "model",
    "base_url_summary",
    "fallback_reason",
    "error_type",
    "outcome",
    "audit_event_id",
    "audit_event_type",
    "runtime_metric_keys",
    "log_request_id",
    "trace_id",
    "report_artifacts",
    "evidence_notes",
    "score",
    "passed",
    "confidence",
    "judge_provider",
}
_DSN_SCHEME_PATTERN = re.compile(r"^(postgresql(?:\+psycopg)?|redis)$", re.IGNORECASE)


@dataclass
class PilotReportCase:
    scenario: str
    endpoint: str
    request_id: str
    provider: str
    model: str
    base_url_summary: str
    api_key_env: str
    api_key_present: bool
    real_call_attempted: bool
    real_call_succeeded: bool
    fallback_used: bool
    fallback_reason: str
    budget_action: str
    cache_hit: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    error_type: str
    outcome: str
    warnings: list[str] = field(default_factory=list)
    evidence_links: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)
    evidence_notes: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        payload["evidence_notes"] = list(self.evidence_notes)
        payload["evidence_links"] = sanitize_pilot_report_payload(dict(self.evidence_links or {}))
        payload["observability"] = sanitize_pilot_report_payload(dict(self.observability or {}))
        payload["detail"] = sanitize_pilot_report_payload(dict(self.detail or {}))
        return payload


@dataclass
class PilotReportArtifact:
    format: str
    path: str
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PilotReportSummary:
    report_id: str
    generated_at: str
    commit: str
    environment: str
    provider: str
    model: str
    base_url_summary: str
    api_key_env: str
    api_key_present: bool
    scenario: str
    endpoint: str
    request_id: str
    real_call_attempted: bool
    real_call_succeeded: bool
    fallback_used: bool
    fallback_reason: str
    budget_action: str
    cache_hit: bool
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    error_type: str
    outcome: str
    warnings: list[str] = field(default_factory=list)
    evidence_links: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)
    evidence_notes: list[str] = field(default_factory=list)
    cases: list[PilotReportCase] = field(default_factory=list)
    artifacts: list[PilotReportArtifact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "commit": self.commit,
            "environment": self.environment,
            "provider": self.provider,
            "model": self.model,
            "base_url_summary": self.base_url_summary,
            "api_key_env": self.api_key_env,
            "api_key_present": self.api_key_present,
            "scenario": self.scenario,
            "endpoint": self.endpoint,
            "request_id": self.request_id,
            "real_call_attempted": self.real_call_attempted,
            "real_call_succeeded": self.real_call_succeeded,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "budget_action": self.budget_action,
            "cache_hit": self.cache_hit,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "error_type": self.error_type,
            "outcome": self.outcome,
            "warnings": list(self.warnings),
            "evidence_links": sanitize_pilot_report_payload(dict(self.evidence_links or {})),
            "observability": sanitize_pilot_report_payload(dict(self.observability or {})),
            "evidence_notes": list(self.evidence_notes),
            "cases": [case.to_dict() for case in self.cases],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "report_artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_datetime(value: datetime | None) -> str:
    if value is None:
        return _utc_now_iso()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _safe_filename_component(text: str, fallback: str = "pilot") -> str:
    normalized = re.sub(r"[^0-9A-Za-z_.-]+", "-", (text or "").strip())
    normalized = normalized.strip("-._")
    return normalized or fallback


def _redact_dsn_if_needed(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text or "://" not in text:
        return value

    try:
        parsed = urlsplit(text)
    except Exception:
        return value

    if not _DSN_SCHEME_PATTERN.match(parsed.scheme or ""):
        return value

    if parsed.password is None:
        return value

    safe_user = parsed.username or "user"
    safe_userinfo = f"{safe_user}:***"
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    safe_netloc = f"{safe_userinfo}@{host}{port}"
    return urlunsplit((parsed.scheme, safe_netloc, parsed.path, parsed.query, parsed.fragment))


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    if key_lower in PILOT_EVIDENCE_SAFE_KEYS:
        return False
    return key_lower in SENSITIVE_KEYS_EXACT or any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS)


def _is_prompt_like_key(key: str) -> bool:
    key_lower = key.lower()
    if key_lower in PILOT_EVIDENCE_SAFE_KEYS:
        return False
    return any(pattern in key_lower for pattern in PROMPT_FIELD_PATTERNS)


def sanitize_pilot_report_payload(payload: Any) -> Any:
    """脱敏试点报告负载，保证不输出 prompt 与密钥原文。"""

    if payload is None:
        return None

    if is_dataclass(payload):
        payload = asdict(payload)

    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key)
            if _is_prompt_like_key(key_text):
                sanitized[key_text] = REDACTED_PROMPT_PLACEHOLDER
                continue
            if _is_sensitive_key(key_text):
                sanitized[key_text] = redact_sensitive_value(value)
                continue
            sanitized[key_text] = sanitize_pilot_report_payload(value)
        return sanitized

    if isinstance(payload, list):
        return [sanitize_pilot_report_payload(item) for item in payload]

    return _redact_dsn_if_needed(payload)


def summarize_base_url(base_url: str) -> str:
    text = (base_url or "").strip()
    if not text:
        return "provider_default"

    try:
        parsed = urlsplit(text)
    except Exception:
        return "invalid_base_url"

    if not parsed.scheme or not parsed.netloc:
        return "custom_base_url"

    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}"


def build_pilot_report(
    *,
    cases: list[PilotReportCase],
    commit: str,
    environment: str,
    report_id: str | None = None,
    generated_at: datetime | None = None,
) -> PilotReportSummary:
    if not cases:
        raise ValueError("cases 不能为空")

    primary = cases[0]
    report_identifier = _safe_filename_component(report_id or f"pilot-{primary.request_id or 'report'}")
    generated_at_text = _normalize_datetime(generated_at)

    return PilotReportSummary(
        report_id=report_identifier,
        generated_at=generated_at_text,
        commit=(commit or "").strip() or "unknown",
        environment=(environment or "").strip() or "unknown",
        provider=primary.provider,
        model=primary.model,
        base_url_summary=primary.base_url_summary,
        api_key_env=primary.api_key_env,
        api_key_present=bool(primary.api_key_present),
        scenario=primary.scenario,
        endpoint=primary.endpoint,
        request_id=primary.request_id,
        real_call_attempted=bool(primary.real_call_attempted),
        real_call_succeeded=bool(primary.real_call_succeeded),
        fallback_used=bool(primary.fallback_used),
        fallback_reason=primary.fallback_reason,
        budget_action=primary.budget_action,
        cache_hit=bool(primary.cache_hit),
        latency_ms=float(primary.latency_ms),
        prompt_tokens=int(primary.prompt_tokens),
        completion_tokens=int(primary.completion_tokens),
        total_tokens=int(primary.total_tokens),
        cost=float(primary.cost),
        error_type=primary.error_type,
        outcome=primary.outcome,
        warnings=list(primary.warnings),
        evidence_links=dict(primary.evidence_links or {}),
        observability=dict(primary.observability or {}),
        evidence_notes=list(primary.evidence_notes or []),
        cases=cases,
        artifacts=[],
    )


def _normalize_output_dir(output_dir: str | Path | None) -> Path:
    if output_dir is None:
        return DEFAULT_PILOT_REPORT_DIR
    return Path(output_dir)


def _report_payload(report: PilotReportSummary | dict[str, Any]) -> dict[str, Any]:
    if isinstance(report, PilotReportSummary):
        payload = report.to_dict()
    else:
        payload = dict(report)
    return sanitize_pilot_report_payload(payload)


def _report_file_stem(payload: dict[str, Any]) -> str:
    generated_at = str(payload.get("generated_at") or _utc_now_iso())
    timestamp = _safe_filename_component(generated_at.replace(":", "-").replace("+", "_"), fallback="report")
    report_id = _safe_filename_component(str(payload.get("report_id") or "pilot"), fallback="pilot")
    return f"{timestamp}_{report_id}"


def write_pilot_report_json(
    report: PilotReportSummary | dict[str, Any],
    *,
    output_dir: str | Path | None = None,
) -> Path:
    payload = _report_payload(report)
    target_dir = _normalize_output_dir(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / f"{_report_file_stem(payload)}.json"
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if isinstance(report, PilotReportSummary):
        report.artifacts.append(
            PilotReportArtifact(format="json", path=str(file_path), generated_at=str(payload.get("generated_at", "")))
        )
    return file_path


def write_pilot_report_markdown(
    report: PilotReportSummary | dict[str, Any],
    *,
    output_dir: str | Path | None = None,
) -> Path:
    payload = _report_payload(report)
    target_dir = _normalize_output_dir(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{_report_file_stem(payload)}.md"

    lines: list[str] = [
        "# Real LLM Controlled Pilot 报告",
        "",
        "- 类型：Controlled Pilot",
        "- 运行方式：opt-in",
        "- 验收边界：not production acceptance",
        "- 数据边界：no raw prompt / no secrets",
        "",
        "## 1. 报告元信息",
        f"- report_id: {payload.get('report_id', '')}",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- commit: {payload.get('commit', '')}",
        f"- environment: {payload.get('environment', '')}",
        "",
        "## 2. 主案例摘要",
        f"- provider/model: {payload.get('provider', '')} / {payload.get('model', '')}",
        f"- endpoint: {payload.get('endpoint', '')}",
        f"- request_id: {payload.get('request_id', '')}",
        f"- outcome: {payload.get('outcome', '')}",
        f"- real_call_attempted: {payload.get('real_call_attempted', False)}",
        f"- real_call_succeeded: {payload.get('real_call_succeeded', False)}",
        f"- fallback_used: {payload.get('fallback_used', False)}",
        f"- fallback_reason: {payload.get('fallback_reason', '')}",
        f"- budget_action: {payload.get('budget_action', '')}",
        f"- cache_hit: {payload.get('cache_hit', False)}",
        f"- latency_ms: {payload.get('latency_ms', 0)}",
        f"- tokens(prompt/completion/total): {payload.get('prompt_tokens', 0)}/{payload.get('completion_tokens', 0)}/{payload.get('total_tokens', 0)}",
        f"- cost: {payload.get('cost', 0)}",
        f"- error_type: {payload.get('error_type', '')}",
        "",
        "## 3. 证据链摘要",
        f"- evidence_links: {json.dumps(payload.get('evidence_links', {}), ensure_ascii=False)}",
        f"- runtime_metric_keys: {json.dumps((payload.get('observability', {}) or {}).get('runtime_metric_keys', []), ensure_ascii=False)}",
        f"- evidence_notes: {', '.join(payload.get('evidence_notes', [])) if payload.get('evidence_notes') else '无'}",
        "",
        "## 4. 案例明细",
    ]

    for index, case in enumerate(payload.get("cases", []), start=1):
        lines.extend(
            [
                f"### Case {index}: {case.get('scenario', '')}",
                f"- endpoint: {case.get('endpoint', '')}",
                f"- request_id: {case.get('request_id', '')}",
                f"- outcome: {case.get('outcome', '')}",
                f"- fallback_reason: {case.get('fallback_reason', '')}",
                f"- budget_action: {case.get('budget_action', '')}",
                f"- error_type: {case.get('error_type', '')}",
                f"- warnings: {', '.join(case.get('warnings', [])) if case.get('warnings') else '无'}",
                f"- evidence_links: {json.dumps(case.get('evidence_links', {}), ensure_ascii=False)}",
                f"- runtime_metric_keys: {json.dumps((case.get('observability', {}) or {}).get('runtime_metric_keys', []), ensure_ascii=False)}",
                f"- detail_redacted: {json.dumps(case.get('detail', {}), ensure_ascii=False)}",
                "",
            ]
        )

    lines.extend(
        [
            "## 5. 边界声明",
            "- 本报告仅用于受控试点证据归档，不等于真实 LLM 生产验收完成。",
            "- 默认 fake/offline 路径与默认 pytest/CI 行为不受影响。",
            "- 报告已执行脱敏：不包含 prompt 原文、密钥原文、数据库密码原文。",
            "",
        ]
    )

    file_path.write_text("\n".join(lines), encoding="utf-8")
    if isinstance(report, PilotReportSummary):
        report.artifacts.append(
            PilotReportArtifact(
                format="markdown",
                path=str(file_path),
                generated_at=str(payload.get("generated_at", "")),
            )
        )
    return file_path
