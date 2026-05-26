from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


LLMAcceptanceMode = Literal["provider", "nl2sql", "judge", "budget", "cache", "fallback"]


@dataclass
class LLMAcceptanceResult:
    """LLM 验收结果摘要（不包含 prompt 原文与密钥信息）。"""

    mode: LLMAcceptanceMode
    provider: str = ""
    model: str = ""
    real_call_attempted: bool = False
    real_call_succeeded: bool = False
    fallback_used: bool = False
    fallback_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0
    cache_hit: bool = False
    budget_action: str = ""
    error_type: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "real_call_attempted": self.real_call_attempted,
            "real_call_succeeded": self.real_call_succeeded,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "cache_hit": self.cache_hit,
            "budget_action": self.budget_action,
            "error_type": self.error_type,
            "warnings": list(self.warnings),
        }


def summarize_llm_acceptance(
    *,
    mode: LLMAcceptanceMode,
    provider: str = "",
    model: str = "",
    provider_metadata: dict[str, Any] | None = None,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    budget_status: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    error_type: str | None = None,
    real_call_attempted: bool | None = None,
) -> LLMAcceptanceResult:
    """汇总单次 LLM 验收结果，统一字段口径。"""

    metadata = dict(provider_metadata or {})
    prompt_tokens = int(metadata.get("prompt_tokens", 0) or 0)
    completion_tokens = int(metadata.get("completion_tokens", 0) or 0)
    total_tokens = int(metadata.get("total_tokens", prompt_tokens + completion_tokens) or 0)
    cost = float(metadata.get("cost", 0.0) or 0.0)
    latency_ms = float(metadata.get("latency_ms", 0.0) or 0.0)
    cache_hit = bool(metadata.get("cache_hit", False))
    model_name = model or str(metadata.get("model", "") or "")
    provider_name = provider or str(metadata.get("provider", "") or "")
    budget_action = str((budget_status or {}).get("action", "") or "")
    reason = (fallback_reason or "").strip()
    attempted = (
        bool(real_call_attempted)
        if real_call_attempted is not None
        else (not fallback_used and not cache_hit and provider_name not in {"", "fake", "mock"})
    )
    succeeded = attempted and (not fallback_used) and not error_type and bool(prompt_tokens or completion_tokens or metadata)

    return LLMAcceptanceResult(
        mode=mode,
        provider=provider_name,
        model=model_name,
        real_call_attempted=attempted,
        real_call_succeeded=succeeded,
        fallback_used=bool(fallback_used),
        fallback_reason=reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost=cost,
        latency_ms=latency_ms,
        cache_hit=cache_hit,
        budget_action=budget_action,
        error_type=(error_type or "").strip(),
        warnings=list(warnings or []),
    )
