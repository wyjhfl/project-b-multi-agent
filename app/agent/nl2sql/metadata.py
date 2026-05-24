from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings


class SchemaField(BaseModel):
    name: str = Field(..., description="字段名")
    type: str = Field(..., description="字段类型")
    is_primary_key: bool = Field(default=False, description="是否主键")
    sample_values: list[Any] = Field(default_factory=list, description="示例值，最多 3 个")


class SchemaTable(BaseModel):
    name: str = Field(..., description="表名")
    fields: list[SchemaField] = Field(default_factory=list, description="字段列表")
    row_count: int = Field(default=0, description="行数")


class DatabaseSchema(BaseModel):
    tables: list[SchemaTable] = Field(default_factory=list, description="表列表")
    db_path: str = Field(default="", description="数据库路径")


class SchemaMetadataExtractor:
    """Schema 元数据提取器

    从 SQLite 数据库自动读取表名、字段名、字段类型、主键、示例值和行数。
    """

    def extract(self, db_path: str | None = None) -> DatabaseSchema:
        path = db_path or settings.ops_db_path
        if not path or not os.path.exists(path):
            return DatabaseSchema(db_path=path or "")

        tables: list[SchemaTable] = []
        with closing(sqlite3.connect(path)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            table_rows = cur.fetchall()

            for (table_name,) in table_rows:
                fields = self._extract_fields(cur, table_name)
                row_count = self._get_row_count(cur, table_name)
                tables.append(SchemaTable(name=table_name, fields=fields, row_count=row_count))

        return DatabaseSchema(tables=tables, db_path=path)

    def _extract_fields(self, cur: sqlite3.Cursor, table_name: str) -> list[SchemaField]:
        cur.execute(f"PRAGMA table_info('{table_name}')")
        columns = cur.fetchall()

        pk_cols: set[str] = set()
        cur.execute(f"PRAGMA table_xinfo('{table_name}')")
        for col in cur.fetchall():
            if col[5] > 0:
                pk_cols.add(col[1])

        fields: list[SchemaField] = []
        for col in columns:
            cid, name, col_type, not_null, default, pk = col
            sample_values = self._get_sample_values(cur, table_name, name)
            fields.append(SchemaField(
                name=name,
                type=col_type,
                is_primary_key=(name in pk_cols),
                sample_values=sample_values,
            ))
        return fields

    def _get_sample_values(self, cur: sqlite3.Cursor, table_name: str, column_name: str) -> list[Any]:
        try:
            cur.execute(f"SELECT DISTINCT `{column_name}` FROM `{table_name}` LIMIT 3")
            return [row[0] for row in cur.fetchall()]
        except Exception:
            return []

    def _get_row_count(self, cur: sqlite3.Cursor, table_name: str) -> int:
        try:
            cur.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            return cur.fetchone()[0]
        except Exception:
            return 0
