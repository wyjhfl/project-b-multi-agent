from __future__ import annotations

from app.agent.nl2sql.executor import SQLExecutionResult


class SQLResultFormatter:
    """SQL 查询结果格式化器

    将 SQLExecutionResult 格式化为包含 summary 的可读输出。
    """

    def format_summary(self, execution_result: SQLExecutionResult) -> dict:
        if not execution_result.success:
            return {
                "summary": f"查询执行失败: {execution_result.error}",
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
            }

        if execution_result.row_count == 0:
            return {
                "summary": "查询成功，但未返回数据",
                "columns": execution_result.columns,
                "rows": [],
                "row_count": 0,
                "truncated": execution_result.truncated,
            }

        if execution_result.row_count == 1 and len(execution_result.columns) == 1:
            value = execution_result.rows[0][execution_result.columns[0]]
            col_name = execution_result.columns[0]
            return {
                "summary": f"{col_name}: {value}",
                "columns": execution_result.columns,
                "rows": execution_result.rows,
                "row_count": execution_result.row_count,
                "truncated": execution_result.truncated,
            }

        return {
            "summary": f"查询返回 {execution_result.row_count} 行数据",
            "columns": execution_result.columns,
            "rows": execution_result.rows,
            "row_count": execution_result.row_count,
            "truncated": execution_result.truncated,
        }
