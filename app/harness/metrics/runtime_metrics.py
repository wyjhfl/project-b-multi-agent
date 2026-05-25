from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.harness.metrics.metrics_store import SQLiteMetricsStore


@dataclass
class RuntimeMetricsRecorder:
    task_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    waiting_approval_count: int = 0
    cancelled_count: int = 0
    unknown_status_count: int = 0
    tool_call_count: int = 0
    tool_failure_count: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost: float = 0.0
    reflection_count: int = 0
    reflection_failed_count: int = 0
    skill_match_count: int = 0
    llm_cache_hit_count: int = 0
    llm_cache_miss_count: int = 0
    budget_status_by_mode: dict[str, dict] = field(default_factory=dict)
    _task_latencies: list[float] = field(default_factory=list)
    _metrics_store: SQLiteMetricsStore | None = field(default=None, repr=False)

    def set_metrics_store(self, store: SQLiteMetricsStore) -> None:
        self._metrics_store = store

    def record_task(self, task_id: str, mode: str, status: str, latency_ms: float | None = None) -> None:
        self.task_count += 1
        if status in ("completed", "success"):
            self.success_count += 1
        elif status in ("failed", "error"):
            self.failed_count += 1
        elif status in ("waiting_approval",):
            self.waiting_approval_count += 1
        elif status in ("cancelled",):
            self.cancelled_count += 1
        else:
            self.unknown_status_count += 1
        if latency_ms is not None:
            self._task_latencies.append(latency_ms)
        if self._metrics_store is not None:
            try:
                self._metrics_store.append_task_metric(
                    task_id=task_id, mode=mode, status=status, latency_ms=latency_ms,
                )
            except Exception:
                logging.warning("SQLite task metric write failed", exc_info=True)

    def record_tool_call(self, tool_name: str, success: bool, latency_ms: float | None = None, retry_count: int = 0, task_id: str = "") -> None:
        self.tool_call_count += 1
        if not success:
            self.tool_failure_count += 1
        if self._metrics_store is not None:
            try:
                self._metrics_store.append_tool_metric(
                    tool_name=tool_name, success=success, latency_ms=latency_ms, retry_count=retry_count, task_id=task_id,
                )
            except Exception:
                logging.warning("SQLite tool metric write failed", exc_info=True)

    def record_token_usage(self, task_id: str, prompt_tokens: int = 0, completion_tokens: int = 0, cost: float = 0.0) -> None:
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost += cost
        if self._metrics_store is not None:
            try:
                self._metrics_store.append_token_usage(
                    task_id=task_id, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost=cost,
                )
            except Exception:
                logging.warning("SQLite token usage write failed", exc_info=True)

    def record_skill_match(self, count: int = 1) -> None:
        self.skill_match_count += count

    def record_cache_hit(self, mode: str = "unknown") -> None:
        self.llm_cache_hit_count += 1

    def record_cache_miss(self, mode: str = "unknown") -> None:
        self.llm_cache_miss_count += 1

    def set_budget_status(self, mode: str, status: dict) -> None:
        if not mode:
            mode = "unknown"
        self.budget_status_by_mode[mode] = dict(status or {})

    def summary(self) -> dict:
        avg_latency = 0.0
        if self._task_latencies:
            avg_latency = sum(self._task_latencies) / len(self._task_latencies)
        return {
            "task_count": self.task_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "waiting_approval_count": self.waiting_approval_count,
            "cancelled_count": self.cancelled_count,
            "unknown_status_count": self.unknown_status_count,
            "tool_call_count": self.tool_call_count,
            "tool_failure_count": self.tool_failure_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cost": self.total_cost,
            "avg_task_latency_ms": avg_latency,
            "reflection_count": self.reflection_count,
            "reflection_failed_count": self.reflection_failed_count,
            "skill_match_count": self.skill_match_count,
            "cache_hit_count": self.llm_cache_hit_count,
            "cache_miss_count": self.llm_cache_miss_count,
            "budget_status": dict(self.budget_status_by_mode),
        }
