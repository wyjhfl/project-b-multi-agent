from __future__ import annotations

from typing import Any, TypedDict


class GraphRuntimeState(TypedDict, total=False):
    task_id: str
    query: str
    mode: str
    stage: str
    context: dict[str, Any] | None
    plan: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    response: dict[str, Any] | None
    error: str | None
    checkpoint_id: str | None
    checkpoint_status: str | None
