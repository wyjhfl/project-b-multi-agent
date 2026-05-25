from __future__ import annotations

import time

from app.auth.jwt import create_access_token, decode_access_token
from app.auth.models import User, UserRole
from app.auth.password import hash_password, verify_password
from app.storage.user_store import InMemoryUserStore


class TestPassword:

    def test_hash_and_verify(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("secret123")
        assert verify_password("wrong", hashed) is False


class TestJWT:

    def test_create_and_decode_token(self):
        user = User(
            user_id="usr_test",
            username="testuser",
            password_hash="x",
            roles=[UserRole.admin],
        )
        token = create_access_token(user)
        payload = decode_access_token(token)
        assert payload.sub == "testuser"
        assert "admin" in payload.roles

    def test_expired_token_raises(self):
        import jwt as pyjwt
        from app.core.config import settings
        payload = {
            "sub": "testuser",
            "roles": ["admin"],
            "exp": int(time.time()) - 3600,
        }
        token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        try:
            decode_access_token(token)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "expired" in str(e).lower()

    def test_invalid_token_raises(self):
        try:
            decode_access_token("invalid.token.here")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "invalid" in str(e).lower()


class TestUserStore:

    def test_create_user(self):
        store = InMemoryUserStore()
        user = store.create_user("admin", "pass123", [UserRole.admin])
        assert user.username == "admin"
        assert user.roles == [UserRole.admin]

    def test_create_duplicate_user_raises(self):
        store = InMemoryUserStore()
        store.create_user("admin", "pass123", [UserRole.admin])
        try:
            store.create_user("admin", "other", [UserRole.viewer])
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_authenticate_success(self):
        store = InMemoryUserStore()
        store.create_user("admin", "pass123", [UserRole.admin])
        user = store.authenticate_user("admin", "pass123")
        assert user is not None
        assert user.username == "admin"

    def test_authenticate_wrong_password(self):
        store = InMemoryUserStore()
        store.create_user("admin", "pass123", [UserRole.admin])
        user = store.authenticate_user("admin", "wrong")
        assert user is None

    def test_authenticate_nonexistent_user(self):
        store = InMemoryUserStore()
        user = store.authenticate_user("nobody", "pass")
        assert user is None

    def test_authenticate_disabled_user(self):
        store = InMemoryUserStore()
        store.create_user("disabled", "pass123", [UserRole.viewer], disabled=True)
        user = store.authenticate_user("disabled", "pass123")
        assert user is None

    def test_seed_default_admin(self):
        store = InMemoryUserStore()
        store.seed_default_admin_if_empty()
        admin = store.get_user_by_username("admin")
        assert admin is not None
        assert UserRole.admin in admin.roles

    def test_seed_not_overwrite(self):
        store = InMemoryUserStore()
        store.create_user("admin", "original", [UserRole.viewer])
        store.seed_default_admin_if_empty()
        admin = store.get_user_by_username("admin")
        assert UserRole.viewer in admin.roles


class TestAuthAPI:

    def test_login_success(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_me_without_token(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        login_resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        token = login_resp.json()["access_token"]
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert "admin" in data["roles"]

    def test_me_with_invalid_token(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401
