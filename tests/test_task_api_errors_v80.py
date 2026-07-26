from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FRONTEND_TASK_DETAIL_PAGE = (
    Path(__file__).parent.parent / "frontend" / "src" / "app" / "tasks" / "[taskId]" / "page.tsx"
)


def test_get_task_not_found_returns_404_with_error_body():
    resp = client.get(f"/tasks/{uuid.uuid4().hex}")
    assert resp.status_code == 404
    data = resp.json()
    assert "不存在" in data["error"]


def test_get_task_existing_returns_200():
    create_resp = client.post(
        "/tasks",
        json={"query": "今天GMV多少", "mode": "keyword", "generator": "mock"},
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["task_id"]

    resp = client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == task_id


def test_task_detail_page_handles_404_without_double_assertion():
    text = FRONTEND_TASK_DETAIL_PAGE.read_text(encoding="utf-8")
    assert "as unknown as { error?: string }" not in text
    assert "ApiError" in text
    assert "404" in text
