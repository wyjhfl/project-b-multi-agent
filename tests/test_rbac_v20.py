from __future__ import annotations

from app.auth.dependencies import DevUser, ROLE_HIERARCHY, ENDPOINT_PERMISSIONS, require_permission
from app.auth.models import TokenPayload


class TestRBACDependencies:

    def test_dev_user_has_admin_role(self):
        dev = DevUser()
        assert dev.username == "system"
        assert "admin" in dev.roles

    def test_role_hierarchy_admin(self):
        assert ROLE_HIERARCHY["admin"] == {"admin", "operator", "viewer", "auditor"}

    def test_role_hierarchy_operator(self):
        assert ROLE_HIERARCHY["operator"] == {"operator", "viewer"}

    def test_role_hierarchy_auditor(self):
        assert ROLE_HIERARCHY["auditor"] == {"auditor", "viewer"}

    def test_role_hierarchy_viewer(self):
        assert ROLE_HIERARCHY["viewer"] == {"viewer"}

    def test_endpoint_permissions_tasks_create(self):
        assert "admin" in ENDPOINT_PERMISSIONS["tasks:create"]
        assert "operator" in ENDPOINT_PERMISSIONS["tasks:create"]
        assert "viewer" not in ENDPOINT_PERMISSIONS["tasks:create"]

    def test_endpoint_permissions_approvals_decide(self):
        assert "admin" in ENDPOINT_PERMISSIONS["approvals:decide"]
        assert "operator" in ENDPOINT_PERMISSIONS["approvals:decide"]
        assert "viewer" not in ENDPOINT_PERMISSIONS["approvals:decide"]

    def test_endpoint_permissions_audit_read(self):
        assert "admin" in ENDPOINT_PERMISSIONS["audit:read"]
        assert "auditor" in ENDPOINT_PERMISSIONS["audit:read"]
        assert "operator" not in ENDPOINT_PERMISSIONS["audit:read"]

    def test_endpoint_permissions_metrics_read(self):
        assert "viewer" in ENDPOINT_PERMISSIONS["metrics:read"]
        assert "operator" in ENDPOINT_PERMISSIONS["metrics:read"]
        assert "admin" in ENDPOINT_PERMISSIONS["metrics:read"]
        assert "auditor" in ENDPOINT_PERMISSIONS["metrics:read"]

    def test_endpoint_permissions_tools_call(self):
        assert "admin" in ENDPOINT_PERMISSIONS["tools:call"]
        assert "operator" in ENDPOINT_PERMISSIONS["tools:call"]
        assert "viewer" not in ENDPOINT_PERMISSIONS["tools:call"]

    def test_endpoint_permissions_tools_read(self):
        assert "admin" in ENDPOINT_PERMISSIONS["tools:read"]
        assert "operator" in ENDPOINT_PERMISSIONS["tools:read"]
        assert "viewer" in ENDPOINT_PERMISSIONS["tools:read"]
        assert "auditor" in ENDPOINT_PERMISSIONS["tools:read"]


class TestRBACWithAuthDisabled:

    def test_tasks_post_without_token(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/tasks", json={"query": "今天GMV多少"})
        assert resp.status_code in (200, 201)

    def test_health_always_ok(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200


class TestRBACAPIIntegration:

    def _token(self, username: str, role: str) -> str:
        from app.auth.jwt import create_access_token
        from app.auth.models import User, UserRole
        user = User(user_id=f"usr_{username}", username=username, password_hash="x", roles=[UserRole(role)])
        return create_access_token(user)

    def _client(self, monkeypatch, *, auth_enabled: bool, rbac_enabled: bool):
        from fastapi.testclient import TestClient
        from app.core.config import settings
        from app.main import app, reset_runtime_for_test
        monkeypatch.setattr(settings, "auth_enabled", auth_enabled)
        monkeypatch.setattr(settings, "rbac_enabled", rbac_enabled)
        monkeypatch.setattr(settings, "storage_backend", "sqlite")
        monkeypatch.setattr(settings, "database_url", "")
        reset_runtime_for_test()
        return TestClient(app)

    def test_auth_disabled_post_tasks_without_token_still_succeeds(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=False, rbac_enabled=False)
        resp = client.post("/tasks", json={"query": "??GMV??"})
        assert resp.status_code in (200, 201)

    def test_auth_enabled_post_tasks_without_token_returns_401(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=False)
        resp = client.post("/tasks", json={"query": "??GMV??"})
        assert resp.status_code == 401

    def test_viewer_cannot_create_task_when_rbac_enabled(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=True)
        token = self._token("viewer", "viewer")
        resp = client.post("/tasks", json={"query": "??GMV??"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_operator_can_create_task_when_rbac_enabled(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=True)
        token = self._token("operator", "operator")
        resp = client.post("/tasks", json={"query": "??GMV??"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201)

    def test_auditor_can_read_audit_events(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=True)
        token = self._token("auditor", "auditor")
        resp = client.get("/audit/events", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_operator_cannot_read_audit_events(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=True)
        token = self._token("operator", "operator")
        resp = client.get("/audit/events", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_viewer_can_read_runtime_metrics(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=True)
        token = self._token("viewer", "viewer")
        resp = client.get("/metrics/runtime", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_viewer_cannot_call_tools(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=True)
        token = self._token("viewer", "viewer")
        resp = client.post("/tools/date_lookup/call", json={"arguments": {}}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_viewer_can_list_tools(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=True)
        token = self._token("viewer", "viewer")
        resp = client.get("/tools", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_auth_enabled_list_tools_without_token_returns_401(self, monkeypatch):
        client = self._client(monkeypatch, auth_enabled=True, rbac_enabled=False)
        resp = client.get("/tools")
        assert resp.status_code == 401
