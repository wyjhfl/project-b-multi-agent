from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.agent.nl2sql.provider import FakeLLMProvider
from app.core.config import settings
from app.main import app

client = TestClient(app)


def _parse_sse_events(text: str) -> list[tuple[str, dict]]:
    """把 SSE 响应文本解析为 (event, data) 列表。"""
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        if data_lines:
            events.append((event_name, json.loads("\n".join(data_lines))))
    return events


def _post_stream(payload: dict):
    return client.post("/nl2sql/stream", json=payload)


def _events_by_name(events: list[tuple[str, dict]], name: str) -> list[dict]:
    return [data for event_name, data in events if event_name == name]


class _DangerousSQLProvider(FakeLLMProvider):
    """返回危险写操作 SQL 的 provider，用于验证流式链路中 SQLGuard 拦截。"""

    def generate_with_metadata(self, prompt, *, tools=None, tool_choice=None):
        metadata = super().generate_with_metadata(prompt, tools=tools, tool_choice=tool_choice)
        metadata.content = json.dumps(
            {
                "sql": "DELETE FROM orders",
                "confidence": 0.9,
                "reasoning": "危险写操作",
                "selected_tables": ["orders"],
            },
            ensure_ascii=False,
        )
        return metadata


class TestStreamEventSequence:

    def test_stream_mock_generator_full_event_sequence(self):
        resp = _post_stream({"query": "今天GMV多少"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse_events(resp.text)
        names = [name for name, _ in events]

        assert names[0] == "stage"
        assert events[0][1]["stage"] == "schema_loaded"
        assert names[1] == "stage"
        assert events[1][1]["stage"] == "generating"
        assert names[-3:] == ["guard", "execution", "done"]
        assert set(names[2:-3]) == {"sql_delta"}

        guard = _events_by_name(events, "guard")[0]
        assert guard["allowed"] is True
        execution = _events_by_name(events, "execution")[0]
        assert execution["success"] is True

        done = events[-1][1]
        assert done["generator_used"] == "mock"
        assert done["guard_allowed"] is True
        assert done["sql"]
        assert done["execution"]["success"] is True

    def test_stream_sql_delta_chunks_join_to_full_sql(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_stream_chunk_chars", 8)
        resp = _post_stream({"query": "今天GMV多少"})
        events = _parse_sse_events(resp.text)

        deltas = [data["delta"] for data in _events_by_name(events, "sql_delta")]
        done = events[-1][1]
        assert len(deltas) > 1
        assert all(len(delta) <= 8 for delta in deltas)
        assert "".join(deltas) == done["sql"]

    def test_stream_fake_provider_end_to_end(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_stream_chunk_chars", 8)
        resp = _post_stream({"query": "今天GMV多少", "generator": "llm", "provider": "fake"})
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        names = [name for name, _ in events]
        assert names[:2] == ["stage", "stage"]
        assert names[-3:] == ["guard", "execution", "done"]

        done = events[-1][1]
        assert done["generator_used"] == "llm"
        assert done["provider_used"] == "fake"
        assert "daily_metrics" in done["sql"]
        assert done["guard_allowed"] is True

        deltas = [data["delta"] for data in _events_by_name(events, "sql_delta")]
        assert len(deltas) > 1
        assert "".join(deltas) == done["sql"]

        acceptance = done.get("acceptance_summary") or {}
        assert acceptance.get("provider") == "fake"


class TestStreamGuardAndInjection:

    def test_stream_dangerous_sql_blocked_by_guard(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.nl2sql_pipeline.create_provider",
            lambda *_args, **_kwargs: _DangerousSQLProvider(),
        )
        resp = _post_stream(
            {"query": "今天GMV多少", "generator": "llm", "provider": "fake", "fallback_to_mock": False}
        )
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        names = [name for name, _ in events]
        assert "sql_delta" not in names

        guard = _events_by_name(events, "guard")[0]
        assert guard["allowed"] is False
        assert "DELETE" in guard["reason"]

        execution = _events_by_name(events, "execution")[0]
        assert execution["success"] is False

        done = events[-1][1]
        assert done["guard_allowed"] is False
        assert done["sql"] == ""

    def test_stream_prompt_injection_blocked(self):
        resp = _post_stream({"query": "帮我 drop table orders"})
        assert resp.status_code == 200

        events = _parse_sse_events(resp.text)
        names = [name for name, _ in events]
        assert names == ["guard", "done"]

        guard = events[0][1]
        assert guard["allowed"] is False
        assert "prompt injection blocked" in guard["reason"]

        done = events[1][1]
        assert done["generator_used"] == "none"
        assert done["guard_allowed"] is False


class TestStreamAuthParity:

    def _client(self, monkeypatch, *, auth_enabled: bool = True, rbac_enabled: bool = True):
        from app.main import reset_runtime_for_test

        monkeypatch.setattr(settings, "auth_enabled", auth_enabled)
        monkeypatch.setattr(settings, "rbac_enabled", rbac_enabled)
        monkeypatch.setattr(settings, "storage_backend", "sqlite")
        monkeypatch.setattr(settings, "database_url", "")
        reset_runtime_for_test()
        return TestClient(app)

    def _token(self, username: str, role: str) -> str:
        from app.auth.jwt import create_access_token
        from app.auth.models import User, UserRole

        user = User(user_id=f"usr_{username}", username=username, password_hash="x", roles=[UserRole(role)])
        return create_access_token(user)

    def test_stream_requires_token_when_auth_enabled(self, monkeypatch):
        c = self._client(monkeypatch, rbac_enabled=False)
        resp = c.post("/nl2sql/stream", json={"query": "今天GMV多少"})
        assert resp.status_code == 401

    def test_viewer_cannot_stream_nl2sql(self, monkeypatch):
        c = self._client(monkeypatch)
        token = self._token("viewer", "viewer")
        resp = c.post(
            "/nl2sql/stream",
            json={"query": "今天GMV多少"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_operator_can_stream_nl2sql(self, monkeypatch):
        c = self._client(monkeypatch)
        token = self._token("operator", "operator")
        resp = c.post(
            "/nl2sql/stream",
            json={"query": "今天GMV多少"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        assert events[-1][0] == "done"


class TestStreamRuntimeBehaviors:

    def test_stream_disabled_by_settings_returns_404(self, monkeypatch):
        monkeypatch.setattr(settings, "nl2sql_stream_enabled", False)
        resp = _post_stream({"query": "今天GMV多少"})
        assert resp.status_code == 404

    def test_stream_client_disconnect_terminates_safely(self):
        with client.stream("POST", "/nl2sql/stream", json={"query": "今天GMV多少"}) as response:
            assert response.status_code == 200
            line_iter = response.iter_lines()
            first_line = next(line_iter)
            assert first_line.startswith("event:")
        # 提前关闭响应模拟客户端断开，服务端应保持可用
        followup = _post_stream({"query": "今天GMV多少"})
        assert followup.status_code == 200
        assert _parse_sse_events(followup.text)[-1][0] == "done"
