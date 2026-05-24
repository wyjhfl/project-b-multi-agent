from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BadCase(BaseModel):
    suite: str
    case_id: str
    query: str
    expected: str
    actual: str
    reason: str
    trace_task_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
