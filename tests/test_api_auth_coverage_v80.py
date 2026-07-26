from __future__ import annotations

import re

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.auth.dependencies import ENDPOINT_PERMISSIONS

# 无需鉴权的公开端点：健康检查、登录入口、OIDC 配置状态（登录页需在拿到 token 前读取）
PUBLIC_PATHS = {"/health", "/auth/login", "/auth/oidc/status"}


def _iter_protected_routes():
    from app.main import app

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path in PUBLIC_PATHS:
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            yield route.path, method


class TestEndpointPermissionAdditions:

    def test_endpoint_permissions_eval_run(self):
        assert "admin" in ENDPOINT_PERMISSIONS["eval:run"]
        assert "operator" in ENDPOINT_PERMISSIONS["eval:run"]
        assert "viewer" not in ENDPOINT_PERMISSIONS["eval:run"]

    def test_endpoint_permissions_memory_read(self):
        assert ENDPOINT_PERMISSIONS["memory:read"] == {"admin", "operator", "viewer", "auditor"}

    def test_endpoint_permissions_nl2sql_run(self):
        assert ENDPOINT_PERMISSIONS["nl2sql:run"] == {"admin", "operator"}

    def test_endpoint_permissions_skills_read(self):
        assert ENDPOINT_PERMISSIONS["skills:read"] == {"admin", "operator", "viewer", "auditor"}

    def test_endpoint_permissions_snapshot_read(self):
        assert ENDPOINT_PERMISSIONS["snapshot:read"] == {"admin", "operator", "viewer", "auditor"}


class TestAuthCoverage:

    def _client(self, monkeypatch, *, auth_enabled: bool, rbac_enabled: bool):
        from app.core.config import settings
        from app.main import app, reset_runtime_for_test

        monkeypatch.setattr(settings, "auth_enabled", auth_enabled)
        monkeypatch.setattr(settings, "rbac_enabled", rbac_enabled)
        monkeypatch.setattr(settings, "storage_backend", "sqlite")
        monkeypatch.setattr(settings, "database_url", "")
        reset_runtime_for_test()
        return TestClient(app)

    def test_all_endpoints_require_token_when_auth_enabled(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=False)
        checked = 0
        for path, method in _iter_protected_routes():
            url = re.sub(r"\{[^}]+\}", "test-id", path)
            body = {} if method in {"POST", "PUT", "PATCH"} else None
            resp = client.request(method, url, json=body)
            assert resp.status_code == 401, f"{method} {path} 未受鉴权保护，实际返回 {resp.status_code}"
            checked += 1
        assert checked >= 40

    def test_public_paths_do_not_require_token(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=False)
        assert client.get("/health").status_code == 200
        assert client.get("/auth/oidc/status").status_code == 200

    def test_auth_disabled_keeps_read_endpoints_open(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=False, rbac_enabled=False)
        assert client.get("/eval/summary").status_code == 200
        assert client.get("/eval/bad-cases").status_code == 200
        assert client.get("/skills").status_code == 200
        assert client.get("/memory/session-demo").status_code == 200
        assert client.get("/observability/tasks/summary").status_code == 200
        assert client.get("/observability/events").status_code == 200
        assert client.get("/runtime/snapshot").status_code == 200
        assert client.get("/llm/preflight").status_code == 200

    def test_auth_disabled_keeps_write_endpoints_open(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=False, rbac_enabled=False)
        resp = client.post("/skills/match", json={"query": "查询今天GMV"})
        assert resp.status_code == 200
        resp = client.post("/nl2sql/preview", json={"query": "今天GMV多少"})
        assert resp.status_code == 200


class TestRBACNewEndpoints:

    def _token(self, username: str, role: str) -> str:
        from app.auth.jwt import create_access_token
        from app.auth.models import User, UserRole
        user = User(user_id=f"usr_{username}", username=username, password_hash="x", roles=[UserRole(role)])
        return create_access_token(user)

    def _client(self, monkeypatch):
        from app.core.config import settings
        from app.main import app, reset_runtime_for_test

        monkeypatch.setattr(settings, "auth_enabled", True)
        monkeypatch.setattr(settings, "rbac_enabled", True)
        monkeypatch.setattr(settings, "storage_backend", "sqlite")
        monkeypatch.setattr(settings, "database_url", "")
        reset_runtime_for_test()
        return TestClient(app)

    def test_viewer_cannot_run_all_evals(self, monkeypatch):
        client = self._client(monkeypatch)
        token = self._token("viewer", "viewer")
        resp = client.post("/eval/run-all", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_viewer_cannot_clear_memory(self, monkeypatch):
        client = self._client(monkeypatch)
        token = self._token("viewer", "viewer")
        resp = client.delete("/memory/session-demo", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_viewer_cannot_execute_nl2sql(self, monkeypatch):
        client = self._client(monkeypatch)
        token = self._token("viewer", "viewer")
        resp = client.post(
            "/nl2sql/execute",
            json={"query": "今天GMV多少"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_viewer_can_read_eval_summary(self, monkeypatch):
        client = self._client(monkeypatch)
        token = self._token("viewer", "viewer")
        resp = client.get("/eval/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_viewer_can_read_memory(self, monkeypatch):
        client = self._client(monkeypatch)
        token = self._token("viewer", "viewer")
        resp = client.get("/memory/session-demo", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_auditor_can_read_observability_events(self, monkeypatch):
        client = self._client(monkeypatch)
        token = self._token("auditor", "auditor")
        resp = client.get("/observability/events", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_operator_can_run_reflection_check(self, monkeypatch):
        client = self._client(monkeypatch)
        token = self._token("operator", "operator")
        resp = client.post(
            "/reflection/check",
            json={"task_result": {"status": "completed"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
