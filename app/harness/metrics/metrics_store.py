from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from typing import Any


class SQLiteMetricsStore:
    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            from app.core.config import settings
            db_path = getattr(settings, "metrics_db_path", None) or os.path.join(
                "data", "db", "runtime_metrics.sqlite"
            )
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        dir_name = os.path.dirname(self._db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_task_metrics (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    latency_ms REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_tool_metrics (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    task_id TEXT NOT NULL DEFAULT '',
                    tool_name TEXT NOT NULL DEFAULT '',
                    success INTEGER NOT NULL DEFAULT 1,
                    latency_ms REAL,
                    retry_count INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runtime_token_usage (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    task_id TEXT NOT NULL DEFAULT '',
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    cost REAL NOT NULL DEFAULT 0.0
                )
            """)
            conn.commit()

    def append_task_metric(
        self,
        task_id: str,
        mode: str,
        status: str,
        latency_ms: float | None = None,
        timestamp: str | None = None,
    ) -> None:
        event_id = uuid.uuid4().hex
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO runtime_task_metrics
                   (event_id, timestamp, task_id, mode, status, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_id, ts, task_id, mode, status, latency_ms),
            )
            conn.commit()

    def append_tool_metric(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float | None = None,
        retry_count: int = 0,
        task_id: str = "",
        timestamp: str | None = None,
    ) -> None:
        event_id = uuid.uuid4().hex
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO runtime_tool_metrics
                   (event_id, timestamp, task_id, tool_name, success, latency_ms, retry_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_id, ts, task_id, tool_name, 1 if success else 0, latency_ms, retry_count),
            )
            conn.commit()

    def append_token_usage(
        self,
        task_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
        timestamp: str | None = None,
    ) -> None:
        event_id = uuid.uuid4().hex
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO runtime_token_usage
                   (event_id, timestamp, task_id, prompt_tokens, completion_tokens, cost)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_id, ts, task_id, prompt_tokens, completion_tokens, cost),
            )
            conn.commit()

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        if limit <= 0:
            return 100
        if limit > 500:
            return 500
        return limit

    def _time_conditions(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> tuple[list[str], list[Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if start_time is not None:
            try:
                datetime.fromisoformat(start_time)
                conditions.append("timestamp >= ?")
                params.append(start_time)
            except (ValueError, TypeError):
                pass
        if end_time is not None:
            try:
                datetime.fromisoformat(end_time)
                conditions.append("timestamp <= ?")
                params.append(end_time)
            except (ValueError, TypeError):
                pass
        return conditions, params

    def summary(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        limit = self._normalize_limit(limit)
        tc, tp = self._time_conditions(start_time, end_time)
        where = f"WHERE {' AND '.join(tc)}" if tc else ""

        result: dict[str, Any] = {
            "task_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "waiting_approval_count": 0,
            "cancelled_count": 0,
            "unknown_status_count": 0,
            "tool_call_count": 0,
            "tool_failure_count": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0,
            "avg_task_latency_ms": 0.0,
        }

        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT status, latency_ms FROM runtime_task_metrics {where} ORDER BY timestamp DESC LIMIT ?",
                tp + [limit],
            )
            latencies: list[float] = []
            for row in cursor.fetchall():
                result["task_count"] += 1
                status = row["status"]
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
                if row["latency_ms"] is not None:
                    latencies.append(row["latency_ms"])
            if latencies:
                result["avg_task_latency_ms"] = sum(latencies) / len(latencies)

            cursor = conn.execute(
                f"SELECT success FROM runtime_tool_metrics {where} ORDER BY timestamp DESC LIMIT ?",
                tp + [limit],
            )
            for row in cursor.fetchall():
                result["tool_call_count"] += 1
                if not row["success"]:
                    result["tool_failure_count"] += 1

            cursor = conn.execute(
                f"SELECT prompt_tokens, completion_tokens, cost FROM runtime_token_usage {where} ORDER BY timestamp DESC LIMIT ?",
                tp + [limit],
            )
            for row in cursor.fetchall():
                result["total_prompt_tokens"] += row["prompt_tokens"]
                result["total_completion_tokens"] += row["completion_tokens"]
                result["total_cost"] += row["cost"]

        return result

    def task_summary(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        limit = self._normalize_limit(limit)
        tc, tp = self._time_conditions(start_time, end_time)
        where = f"WHERE {' AND '.join(tc)}" if tc else ""

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

        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT mode, status, latency_ms FROM runtime_task_metrics {where} ORDER BY timestamp DESC LIMIT ?",
                tp + [limit],
            )
            latencies: list[float] = []
            for row in cursor.fetchall():
                result["task_count"] += 1
                mode = row["mode"] or "unknown"
                status = row["status"]
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
                if mode not in by_mode:
                    by_mode[mode] = {"count": 0, "success_count": 0, "failed_count": 0}
                by_mode[mode]["count"] += 1
                if status in ("completed", "success"):
                    by_mode[mode]["success_count"] += 1
                elif status in ("failed", "error"):
                    by_mode[mode]["failed_count"] += 1
                if row["latency_ms"] is not None:
                    latencies.append(row["latency_ms"])
            if latencies:
                result["avg_task_latency_ms"] = sum(latencies) / len(latencies)

        return result

    def tool_summary(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        limit = self._normalize_limit(limit)
        tc, tp = self._time_conditions(start_time, end_time)
        where = f"WHERE {' AND '.join(tc)}" if tc else ""

        result: dict[str, Any] = {
            "tool_call_count": 0,
            "tool_failure_count": 0,
            "retry_count": 0,
            "avg_latency_ms": 0.0,
            "by_tool": {},
        }

        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                f"SELECT tool_name, success, latency_ms, retry_count FROM runtime_tool_metrics {where} ORDER BY timestamp DESC LIMIT ?",
                tp + [limit],
            )
            latencies: list[float] = []
            for row in cursor.fetchall():
                result["tool_call_count"] += 1
                if not row["success"]:
                    result["tool_failure_count"] += 1
                result["retry_count"] += row["retry_count"]
                if row["latency_ms"] is not None:
                    latencies.append(row["latency_ms"])
                tool_name = row["tool_name"] or "unknown"
                by_tool = result["by_tool"]
                if tool_name not in by_tool:
                    by_tool[tool_name] = {"call_count": 0, "failure_count": 0, "retry_count": 0, "avg_latency_ms": 0.0, "latencies": []}
                by_tool[tool_name]["call_count"] += 1
                if not row["success"]:
                    by_tool[tool_name]["failure_count"] += 1
                by_tool[tool_name]["retry_count"] += row["retry_count"]
                if row["latency_ms"] is not None:
                    by_tool[tool_name]["latencies"].append(row["latency_ms"])
            if latencies:
                result["avg_latency_ms"] = sum(latencies) / len(latencies)
            for tool_data in result["by_tool"].values():
                tool_lats = tool_data.pop("latencies")
                if tool_lats:
                    tool_data["avg_latency_ms"] = sum(tool_lats) / len(tool_lats)

        return result

    def cost_summary(
        self,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        limit = self._normalize_limit(limit)
        tc, tp = self._time_conditions(start_time, end_time)
        where = f"WHERE {' AND '.join(tc)}" if tc else ""

        result: dict[str, Any] = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0,
            "by_mode": {},
            "by_day": {},
        }

        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            task_mode_map: dict[str, str] = {}
            mode_cursor = conn.execute(
                "SELECT task_id, mode FROM runtime_task_metrics ORDER BY timestamp ASC"
            )
            for row in mode_cursor.fetchall():
                if row["task_id"] not in task_mode_map:
                    task_mode_map[row["task_id"]] = row["mode"] or "unknown"

            where_clause = f"WHERE {' AND '.join(tc)}" if tc else ""
            cursor = conn.execute(
                f"SELECT task_id, prompt_tokens, completion_tokens, cost, timestamp "
                f"FROM runtime_token_usage {where_clause} "
                f"ORDER BY timestamp DESC LIMIT ?",
                tp + [limit],
            )
            for row in cursor.fetchall():
                result["total_prompt_tokens"] += row["prompt_tokens"]
                result["total_completion_tokens"] += row["completion_tokens"]
                result["total_cost"] += row["cost"]
                mode = task_mode_map.get(row["task_id"], "unknown")
                by_mode = result["by_mode"]
                if mode not in by_mode:
                    by_mode[mode] = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
                by_mode[mode]["prompt_tokens"] += row["prompt_tokens"]
                by_mode[mode]["completion_tokens"] += row["completion_tokens"]
                by_mode[mode]["cost"] += row["cost"]
                day = row["timestamp"][:10] if row["timestamp"] else "unknown"
                by_day = result["by_day"]
                if day not in by_day:
                    by_day[day] = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
                by_day[day]["prompt_tokens"] += row["prompt_tokens"]
                by_day[day]["completion_tokens"] += row["completion_tokens"]
                by_day[day]["cost"] += row["cost"]

        return result
