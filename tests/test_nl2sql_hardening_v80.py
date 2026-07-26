from __future__ import annotations

import sqlite3

from app.agent.nl2sql.executor import SQLiteReadOnlyExecutor
from app.agent.nl2sql.sql_guard import SQLGuard, SQLGuardResult


def _make_db(tmp_path):
    db_path = tmp_path / "readonly_demo.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount REAL)")
    conn.execute("INSERT INTO orders (amount) VALUES (100.0)")
    conn.commit()
    conn.close()
    return db_path


class TestReadOnlyConnection:

    def test_select_succeeds_on_readonly_connection(self, tmp_path):
        executor = SQLiteReadOnlyExecutor(db_path=str(_make_db(tmp_path)))
        result = executor.execute("SELECT id, amount FROM orders")
        assert result.success is True
        assert result.row_count == 1

    def test_write_rejected_even_if_guard_bypassed(self, tmp_path, monkeypatch):
        db_path = _make_db(tmp_path)
        executor = SQLiteReadOnlyExecutor(db_path=str(db_path))
        # 模拟 SQLGuard 被绕过的最坏情况：连接层必须仍然拒绝写入
        monkeypatch.setattr(
            executor._guard,
            "check",
            lambda sql: SQLGuardResult(allowed=True, sql=sql, reason=""),
        )
        result = executor.execute("INSERT INTO orders (amount) VALUES (999.0)")
        assert result.success is False
        assert "readonly" in (result.error or "").lower()

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        conn.close()
        assert count == 1

    def test_missing_db_file_returns_failure(self, tmp_path):
        executor = SQLiteReadOnlyExecutor(db_path=str(tmp_path / "not_exists.sqlite"))
        result = executor.execute("SELECT 1")
        assert result.success is False
        assert "数据库文件不存在" in result.error


class TestCTEGuard:

    def test_readonly_cte_allowed(self):
        guard = SQLGuard()
        result = guard.check(
            "WITH recent AS (SELECT * FROM orders WHERE order_date = '2024-01-01') SELECT * FROM recent"
        )
        assert result.allowed is True

    def test_with_without_select_blocked(self):
        guard = SQLGuard()
        result = guard.check("WITH x AS (VALUES (1)) VALUES (2)")
        assert result.allowed is False
        assert "SELECT" in result.reason

    def test_cte_with_blocked_keyword_rejected(self):
        guard = SQLGuard()
        result = guard.check("WITH x AS (SELECT 1) DELETE FROM orders")
        assert result.allowed is False
        assert "DELETE" in result.reason
