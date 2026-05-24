from __future__ import annotations

import json
import os

from pydantic import BaseModel, Field


class NL2SQLEvalCase(BaseModel):
    id: str = Field(..., description="用例 ID")
    input: str = Field(..., description="用户输入")
    expected_tables: list[str] = Field(default_factory=list, description="期望选中的表")
    expected_sql_contains: list[str] = Field(default_factory=list, description="SQL 应包含的关键词")
    category: str = Field(default="general", description="用例分类")
    raw_sql: str | None = Field(default=None, description="dangerous_sql 用的原始 SQL")
    expected_blocked_keyword: str | None = Field(default=None, description="期望被拦截的关键字")


class EvalCaseLoader:
    """评测用例加载器

    从 JSON 文件加载 NL2SQL 评测样例。
    """

    def load(self, path: str | None = None) -> list[NL2SQLEvalCase]:
        if path is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            path = os.path.join(base_dir, "data", "evaluation", "nl2sql_cases.json")

        if not os.path.exists(path):
            return []

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return [NL2SQLEvalCase(**item) for item in data]
