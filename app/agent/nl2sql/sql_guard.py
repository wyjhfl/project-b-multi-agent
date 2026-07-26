from __future__ import annotations

import re

from pydantic import BaseModel, Field


class SQLGuardResult(BaseModel):
    allowed: bool = Field(..., description="是否允许执行")
    sql: str = Field(..., description="处理后的 SQL")
    reason: str = Field(default="", description="拦截原因")


class SQLGuard:
    """SQL 安全守卫

    只允许 SELECT 查询（含 WITH ... SELECT 只读 CTE），拦截所有写操作和 DDL。
    防护：空 SQL、多语句注入、注释中的危险关键字、字段名误判。
    自动追加 LIMIT，防止全表扫描。
    """

    BLOCKED_KEYWORDS = [
        "DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE", "ALTER", "CREATE", "PRAGMA",
    ]

    DEFAULT_LIMIT = 100

    def check(self, sql: str) -> SQLGuardResult:
        """检查 SQL 是否安全

        Args:
            sql: 待检查的 SQL

        Returns:
            SQLGuardResult 包含 allowed、sql、reason
        """
        if not sql or not sql.strip():
            return SQLGuardResult(allowed=False, sql=sql, reason="SQL 为空")

        stripped = sql.strip()

        multi_stmt_result = self._check_multi_statement(stripped)
        if multi_stmt_result is not None:
            return multi_stmt_result

        comment_result = self._check_comments(stripped)
        if comment_result is not None:
            return comment_result

        normalized = stripped.upper()

        for keyword in self.BLOCKED_KEYWORDS:
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, normalized):
                return SQLGuardResult(
                    allowed=False,
                    sql=sql,
                    reason=f"SQL 包含被禁止的关键字: {keyword}",
                )

        first_word = normalized.split()[0] if normalized.split() else ""
        if first_word not in ("SELECT", "WITH"):
            return SQLGuardResult(
                allowed=False,
                sql=sql,
                reason=f"只允许 SELECT 或 WITH 查询，当前首词: {first_word}",
            )

        if first_word == "WITH":
            cte_result = self._validate_cte(stripped, normalized)
            if cte_result is not None:
                return cte_result

        safe_sql = self._ensure_limit(stripped)
        return SQLGuardResult(allowed=True, sql=safe_sql, reason="")

    def _check_multi_statement(self, sql: str) -> SQLGuardResult | None:
        without_trailing = sql.rstrip().rstrip(";")
        if ";" in without_trailing:
            return SQLGuardResult(
                allowed=False,
                sql=sql,
                reason="SQL 包含多条语句（检测到非末尾分号）",
            )
        return None

    def _check_comments(self, sql: str) -> SQLGuardResult | None:
        comment_text = self._extract_comment_text(sql)
        if not comment_text:
            return None

        comment_upper = comment_text.upper()
        for keyword in self.BLOCKED_KEYWORDS:
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, comment_upper):
                return SQLGuardResult(
                    allowed=False,
                    sql=sql,
                    reason=f"SQL 注释中包含被禁止的关键字: {keyword}",
                )
        return None

    def _extract_comment_text(self, sql: str) -> str:
        parts: list[str] = []

        for line in sql.split("\n"):
            idx = line.find("--")
            if idx != -1:
                parts.append(line[idx + 2:])

        block_pattern = r'/\*(.*?)\*/'
        for match in re.finditer(block_pattern, sql, re.DOTALL):
            parts.append(match.group(1))

        return " ".join(parts)

    def _validate_cte(self, sql: str, normalized: str) -> SQLGuardResult | None:
        if "SELECT" not in normalized:
            return SQLGuardResult(
                allowed=False,
                sql=sql,
                reason="WITH CTE 必须最终是 SELECT 查询",
            )
        return None

    def _ensure_limit(self, sql: str) -> str:
        if re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
            return sql
        without_semi = sql.rstrip(";").strip()
        return f"{without_semi} LIMIT {self.DEFAULT_LIMIT};"
