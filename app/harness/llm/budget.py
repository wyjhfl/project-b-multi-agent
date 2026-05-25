from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app.core.config import settings


@dataclass
class BudgetDecision:
    allowed: bool
    action: str
    reason: str
    budget_scope: str
    current_cost: float
    soft_limit: float
    hard_limit: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "reason": self.reason,
            "budget_scope": self.budget_scope,
            "current_cost": self.current_cost,
            "soft_limit": self.soft_limit,
            "hard_limit": self.hard_limit,
        }


class LLMBudgetManager:
    """LLM 预算控制器（进程内轻量实现）。"""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        soft_limit: float | None = None,
        hard_limit: float | None = None,
        scope: str | None = None,
    ) -> None:
        self._enabled = settings.llm_budget_enabled if enabled is None else enabled
        self._soft_limit = float(settings.llm_budget_soft_usd if soft_limit is None else soft_limit)
        self._hard_limit = float(settings.llm_budget_hard_usd if hard_limit is None else hard_limit)
        self._scope = (settings.llm_budget_scope if scope is None else scope).strip().lower() or "daily"
        self._lock = Lock()
        self._cost_by_scope: dict[str, float] = {}
        self._usage_events: list[dict[str, Any]] = []

    def _scope_key(self, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        if self._scope == "global":
            return "global"
        if self._scope == "hourly":
            return now.strftime("%Y-%m-%dT%H")
        return now.strftime("%Y-%m-%d")

    def check_budget(
        self,
        mode: str,
        provider: str,
        model: str,
        estimated_cost: float = 0.0,
    ) -> dict[str, Any]:
        if not self._enabled:
            return BudgetDecision(
                allowed=True,
                action="allow",
                reason="budget_disabled",
                budget_scope=self._scope,
                current_cost=0.0,
                soft_limit=self._soft_limit,
                hard_limit=self._hard_limit,
            ).to_dict()

        scope_key = self._scope_key()
        with self._lock:
            current_cost = float(self._cost_by_scope.get(scope_key, 0.0))

        projected_cost = current_cost + max(0.0, float(estimated_cost))
        if self._hard_limit > 0 and projected_cost >= self._hard_limit:
            return BudgetDecision(
                allowed=False,
                action="fallback",
                reason=f"budget_blocked:hard_limit_exceeded:{self._hard_limit}",
                budget_scope=self._scope,
                current_cost=current_cost,
                soft_limit=self._soft_limit,
                hard_limit=self._hard_limit,
            ).to_dict()

        if self._soft_limit > 0 and projected_cost >= self._soft_limit:
            return BudgetDecision(
                allowed=True,
                action="warn",
                reason=f"budget_soft_limit_reached:{self._soft_limit}",
                budget_scope=self._scope,
                current_cost=current_cost,
                soft_limit=self._soft_limit,
                hard_limit=self._hard_limit,
            ).to_dict()

        return BudgetDecision(
            allowed=True,
            action="allow",
            reason="budget_ok",
            budget_scope=self._scope,
            current_cost=current_cost,
            soft_limit=self._soft_limit,
            hard_limit=self._hard_limit,
        ).to_dict()

    def record_usage(
        self,
        mode: str,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
    ) -> None:
        if not self._enabled:
            return
        scope_key = self._scope_key()
        usage = {
            "scope_key": scope_key,
            "mode": mode,
            "provider": provider or "unknown",
            "model": model or "unknown",
            "prompt_tokens": max(0, int(prompt_tokens)),
            "completion_tokens": max(0, int(completion_tokens)),
            "cost": max(0.0, float(cost)),
        }
        with self._lock:
            self._cost_by_scope[scope_key] = float(self._cost_by_scope.get(scope_key, 0.0)) + usage["cost"]
            self._usage_events.append(usage)

    def summary(self) -> dict[str, Any]:
        if not self._enabled:
            return {
                "enabled": False,
                "scope": self._scope,
                "current_cost": 0.0,
                "soft_limit": self._soft_limit,
                "hard_limit": self._hard_limit,
                "by_provider": {},
                "by_model": {},
            }
        scope_key = self._scope_key()
        with self._lock:
            current_cost = float(self._cost_by_scope.get(scope_key, 0.0))
            events = list(self._usage_events)
        by_provider: dict[str, float] = {}
        by_model: dict[str, float] = {}
        for event in events:
            if event.get("scope_key") != scope_key:
                continue
            provider = str(event.get("provider") or "unknown")
            model = str(event.get("model") or "unknown")
            cost = float(event.get("cost") or 0.0)
            by_provider[provider] = by_provider.get(provider, 0.0) + cost
            by_model[model] = by_model.get(model, 0.0) + cost
        return {
            "enabled": True,
            "scope": self._scope,
            "current_cost": current_cost,
            "soft_limit": self._soft_limit,
            "hard_limit": self._hard_limit,
            "by_provider": by_provider,
            "by_model": by_model,
        }


_GLOBAL_BUDGET_MANAGER: LLMBudgetManager | None = None


def get_llm_budget_manager() -> LLMBudgetManager:
    global _GLOBAL_BUDGET_MANAGER
    if _GLOBAL_BUDGET_MANAGER is None:
        _GLOBAL_BUDGET_MANAGER = LLMBudgetManager()
    return _GLOBAL_BUDGET_MANAGER


def reset_llm_budget_manager_for_test() -> None:
    global _GLOBAL_BUDGET_MANAGER
    _GLOBAL_BUDGET_MANAGER = None
