from __future__ import annotations

import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, Field

from app.agent.nl2sql.sql_guard import SQLGuard
from app.core.config import settings


class SQLExecutionResult(BaseModel):
    sql: str = Field(..., description="执行的 SQL")
    columns: list[str] = Field(default_factory=list, description="列名")
    rows: list[dict] = Field(default_factory=list, description="查询结果行")
    row_count: int = Field(default=0, description="返回行数")
    truncated: bool = Field(default=False, description="是否被截断")
    success: bool = Field(..., description="是否执行成功")
    error: str | None = Field(default=None, description="错误信息")
    latency_ms: float = Field(default=0.0, description="执行耗时（毫秒）")


class SQLiteReadOnlyExecutor:
    """SQLite 只读执行器

    只执行通过 SQLGuard 的 SELECT / readonly WITH SELECT。
    不允许执行原始未 guard 的 SQL。
    """

    MAX_ROWS = 100

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or settings.ops_db_path
        self._guard = SQLGuard()

    def _readonly_uri(self) -> str:
        """构造 SQLite 只读连接 URI

        使用 file:...?mode=ro 打开数据库，从连接层面禁止任何写入，
        即使 SQL 绕过 SQLGuard 也无法修改数据。
        """
        return f"{Path(self._db_path).resolve().as_uri()}?mode=ro"

    def execute(self, sql: str) -> SQLExecutionResult:
        guard_result = self._guard.check(sql)

        if not guard_result.allowed:
            return SQLExecutionResult(
                sql=sql,
                success=False,
                error=guard_result.reason,
            )

        safe_sql = guard_result.sql

        if not os.path.exists(self._db_path):
            return SQLExecutionResult(
                sql=safe_sql,
                success=False,
                error=f"数据库文件不存在: {self._db_path}",
            )

        start = time.monotonic()
        try:
            with closing(sqlite3.connect(self._readonly_uri(), uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                with closing(conn.cursor()) as cur:
                    cur.execute(safe_sql)
                    all_rows = cur.fetchall()
                    columns = [desc[0] for desc in cur.description] if cur.description else []
        except sqlite3.OperationalError as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SQLExecutionResult(
                sql=safe_sql,
                success=False,
                error=str(exc),
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return SQLExecutionResult(
                sql=safe_sql,
                success=False,
                error=str(exc),
                latency_ms=round(elapsed, 2),
            )

        elapsed = (time.monotonic() - start) * 1000
        truncated = len(all_rows) > self.MAX_ROWS
        limited_rows = all_rows[:self.MAX_ROWS]

        rows = [dict(row) for row in limited_rows]

        return SQLExecutionResult(
            sql=safe_sql,
            columns=columns,
            rows=rows,
            row_count=len(all_rows),
            truncated=truncated,
            success=True,
            error=None,
            latency_ms=round(elapsed, 2),
        )
