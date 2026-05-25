from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.storage.database import get_session_factory
from app.storage.models import RuntimeTaskMetricRow, RuntimeToolMetricRow, RuntimeTokenUsageRow


class PostgresMetricsStore:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def append_task_metric(
        self,
        task_id: str,
        mode: str,
        status: str,
        latency_ms: float | None = None,
        timestamp: str | None = None,
    ) -> None:
        self.record_task_metric(task_id=task_id, mode=mode, status=status, latency_ms=latency_ms, timestamp=timestamp)

    def append_tool_metric(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float | None = None,
        retry_count: int = 0,
        task_id: str = "",
        timestamp: str | None = None,
    ) -> None:
        self.record_tool_metric(
            task_id=task_id,
            tool_name=tool_name,
            success=success,
            latency_ms=latency_ms,
            retry_count=retry_count,
            timestamp=timestamp,
        )

    def append_token_usage(
        self,
        task_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
        timestamp: str | None = None,
    ) -> None:
        self.record_token_usage(
            task_id=task_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost=cost,
            timestamp=timestamp,
        )

    def record_task_metric(self, **kwargs: Any) -> None:
        with self._session_factory() as session:
            row = RuntimeTaskMetricRow(
                task_id=kwargs.get("task_id", ""),
                mode=kwargs.get("mode", ""),
                status=kwargs.get("status", ""),
                success=1 if kwargs.get("success") else 0,
                latency_ms=kwargs.get("latency_ms"),
                timestamp=self._parse_timestamp(kwargs.get("timestamp")),
            )
            session.add(row)
            session.commit()

    def record_tool_metric(self, **kwargs: Any) -> None:
        with self._session_factory() as session:
            row = RuntimeToolMetricRow(
                task_id=kwargs.get("task_id", ""),
                tool_name=kwargs.get("tool_name", ""),
                success=1 if kwargs.get("success") else 0,
                latency_ms=kwargs.get("latency_ms"),
                retry_count=kwargs.get("retry_count", 0),
                timestamp=self._parse_timestamp(kwargs.get("timestamp")),
            )
            session.add(row)
            session.commit()

    def record_token_usage(self, **kwargs: Any) -> None:
        with self._session_factory() as session:
            row = RuntimeTokenUsageRow(
                task_id=kwargs.get("task_id", ""),
                model_name=kwargs.get("model_name", ""),
                prompt_tokens=kwargs.get("prompt_tokens", 0),
                completion_tokens=kwargs.get("completion_tokens", 0),
                total_cost=kwargs.get("total_cost", kwargs.get("cost", 0.0)),
                timestamp=self._parse_timestamp(kwargs.get("timestamp")),
            )
            session.add(row)
            session.commit()

    def summary(self, start_time: str | None = None, end_time: str | None = None, limit: int = 100) -> dict[str, Any]:
        task_summary = self.task_summary(start_time=start_time, end_time=end_time, limit=limit)
        tool_summary = self.tool_summary(start_time=start_time, end_time=end_time, limit=limit)
        cost_summary = self.cost_summary(start_time=start_time, end_time=end_time, limit=limit)
        return {
            "task_count": task_summary["task_count"],
            "success_count": task_summary["success_count"],
            "failed_count": task_summary["failed_count"],
            "waiting_approval_count": task_summary["waiting_approval_count"],
            "cancelled_count": task_summary["cancelled_count"],
            "unknown_status_count": task_summary["unknown_status_count"],
            "tool_call_count": tool_summary["tool_call_count"],
            "tool_failure_count": tool_summary["tool_failure_count"],
            "total_prompt_tokens": cost_summary["total_prompt_tokens"],
            "total_completion_tokens": cost_summary["total_completion_tokens"],
            "total_cost": cost_summary["total_cost"],
            "avg_task_latency_ms": task_summary["avg_task_latency_ms"],
        }

    def task_summary(self, start_time: str | None = None, end_time: str | None = None, limit: int = 100) -> dict[str, Any]:
        rows = self._task_rows(start_time, end_time, limit)
        result: dict[str, Any] = {
            "task_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "waiting_approval_count": 0,
            "cancelled_count": 0,
            "unknown_status_count": 0,
            "avg_task_latency_ms": 0.0,
            "by_mode": {},
        }
        latencies: list[float] = []
        for row in rows:
            result["task_count"] += 1
            status = row.status or ""
            mode = row.mode or "unknown"
            if status in ("completed", "success"):
                result["success_count"] += 1
            elif status in ("failed", "error"):
                result["failed_count"] += 1
            elif status == "waiting_approval":
                result["waiting_approval_count"] += 1
            elif status == "cancelled":
                result["cancelled_count"] += 1
            else:
                result["unknown_status_count"] += 1
            by_mode = result["by_mode"]
            by_mode.setdefault(mode, {"count": 0, "success_count": 0, "failed_count": 0})
            by_mode[mode]["count"] += 1
            if status in ("completed", "success"):
                by_mode[mode]["success_count"] += 1
            elif status in ("failed", "error"):
                by_mode[mode]["failed_count"] += 1
            if row.latency_ms is not None:
                latencies.append(row.latency_ms)
        if latencies:
            result["avg_task_latency_ms"] = sum(latencies) / len(latencies)
        return result

    def tool_summary(self, start_time: str | None = None, end_time: str | None = None, limit: int = 100) -> dict[str, Any]:
        rows = self._tool_rows(start_time, end_time, limit)
        result: dict[str, Any] = {
            "tool_call_count": 0,
            "tool_failure_count": 0,
            "retry_count": 0,
            "avg_latency_ms": 0.0,
            "by_tool": {},
        }
        latencies: list[float] = []
        for row in rows:
            result["tool_call_count"] += 1
            if not row.success:
                result["tool_failure_count"] += 1
            retry_count = row.retry_count or 0
            result["retry_count"] += retry_count
            if row.latency_ms is not None:
                latencies.append(row.latency_ms)
            tool_name = row.tool_name or "unknown"
            by_tool = result["by_tool"]
            by_tool.setdefault(tool_name, {"call_count": 0, "failure_count": 0, "retry_count": 0, "avg_latency_ms": 0.0, "latencies": []})
            by_tool[tool_name]["call_count"] += 1
            if not row.success:
                by_tool[tool_name]["failure_count"] += 1
            by_tool[tool_name]["retry_count"] += retry_count
            if row.latency_ms is not None:
                by_tool[tool_name]["latencies"].append(row.latency_ms)
        if latencies:
            result["avg_latency_ms"] = sum(latencies) / len(latencies)
        for tool_data in result["by_tool"].values():
            tool_lats = tool_data.pop("latencies")
            if tool_lats:
                tool_data["avg_latency_ms"] = sum(tool_lats) / len(tool_lats)
        return result

    def cost_summary(self, start_time: str | None = None, end_time: str | None = None, limit: int = 100) -> dict[str, Any]:
        rows = self._token_rows(start_time, end_time, limit)
        result: dict[str, Any] = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0,
            "by_mode": {},
            "by_day": {},
        }
        task_modes = self._task_mode_map()
        for row in rows:
            result["total_prompt_tokens"] += row.prompt_tokens or 0
            result["total_completion_tokens"] += row.completion_tokens or 0
            result["total_cost"] += row.total_cost or 0.0
            mode = task_modes.get(row.task_id, "unknown")
            result["by_mode"].setdefault(mode, {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0})
            result["by_mode"][mode]["prompt_tokens"] += row.prompt_tokens or 0
            result["by_mode"][mode]["completion_tokens"] += row.completion_tokens or 0
            result["by_mode"][mode]["cost"] += row.total_cost or 0.0
            day = row.timestamp.date().isoformat() if row.timestamp else "unknown"
            result["by_day"].setdefault(day, {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0})
            result["by_day"][day]["prompt_tokens"] += row.prompt_tokens or 0
            result["by_day"][day]["completion_tokens"] += row.completion_tokens or 0
            result["by_day"][day]["cost"] += row.total_cost or 0.0
        return result

    def get_task_metrics_summary(self, **kwargs: Any) -> dict[str, Any]:
        return self.task_summary(**kwargs)

    def get_tool_metrics_summary(self, **kwargs: Any) -> dict[str, Any]:
        return self.tool_summary(**kwargs)

    def get_token_usage_summary(self, **kwargs: Any) -> dict[str, Any]:
        return self.cost_summary(**kwargs)

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime:
        if value:
            try:
                return datetime.fromisoformat(value)
            except (TypeError, ValueError):
                pass
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        if limit <= 0:
            return 100
        if limit > 500:
            return 500
        return limit

    @staticmethod
    def _apply_time_filters(query, model, start_time: str | None, end_time: str | None):
        if start_time is not None:
            try:
                query = query.filter(model.timestamp >= datetime.fromisoformat(start_time))
            except (TypeError, ValueError):
                pass
        if end_time is not None:
            try:
                query = query.filter(model.timestamp <= datetime.fromisoformat(end_time))
            except (TypeError, ValueError):
                pass
        return query

    def _task_rows(self, start_time: str | None, end_time: str | None, limit: int):
        limit = self._normalize_limit(limit)
        with self._session_factory() as session:
            q = session.query(RuntimeTaskMetricRow)
            q = self._apply_time_filters(q, RuntimeTaskMetricRow, start_time, end_time)
            return q.order_by(RuntimeTaskMetricRow.timestamp.desc()).limit(limit).all()

    def _tool_rows(self, start_time: str | None, end_time: str | None, limit: int):
        limit = self._normalize_limit(limit)
        with self._session_factory() as session:
            q = session.query(RuntimeToolMetricRow)
            q = self._apply_time_filters(q, RuntimeToolMetricRow, start_time, end_time)
            return q.order_by(RuntimeToolMetricRow.timestamp.desc()).limit(limit).all()

    def _token_rows(self, start_time: str | None, end_time: str | None, limit: int):
        limit = self._normalize_limit(limit)
        with self._session_factory() as session:
            q = session.query(RuntimeTokenUsageRow)
            q = self._apply_time_filters(q, RuntimeTokenUsageRow, start_time, end_time)
            return q.order_by(RuntimeTokenUsageRow.timestamp.desc()).limit(limit).all()

    def _task_mode_map(self) -> dict[str, str]:
        with self._session_factory() as session:
            rows = session.query(RuntimeTaskMetricRow.task_id, RuntimeTaskMetricRow.mode).order_by(RuntimeTaskMetricRow.timestamp.asc()).all()
        result: dict[str, str] = {}
        for task_id, mode in rows:
            result.setdefault(task_id, mode or "unknown")
        return result
