from __future__ import annotations

import time

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth.jwt import create_access_token, decode_access_token
from app.auth.models import User, UserRole
from app.auth.password import hash_password, verify_password
from app.storage.models import Base
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

    def test_user_store_factory_uses_memory_by_default(self, monkeypatch):
        from app.core.config import settings
        from app.storage.factory import get_user_store

        monkeypatch.setattr(settings, "storage_backend", "sqlite")
        monkeypatch.setattr(settings, "database_url", "")

        store = get_user_store()
        assert isinstance(store, InMemoryUserStore)

    def test_user_store_factory_uses_postgres_when_configured(self, monkeypatch):
        from app.core.config import settings
        from app.storage.factory import get_user_store
        from app.storage.postgres.user_store import PostgresUserStore

        monkeypatch.setattr(settings, "storage_backend", "postgres")
        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:pass@localhost:5432/project_b")
        monkeypatch.setattr("app.storage.postgres.user_store.get_session_factory", lambda: sessionmaker(class_=Session))

        store = get_user_store()
        assert isinstance(store, PostgresUserStore)


class TestPostgresUserStore:

    def _store(self, tmp_path, monkeypatch):
        from app.storage.postgres.user_store import PostgresUserStore

        db_path = tmp_path / "users.sqlite"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
        monkeypatch.setattr("app.storage.postgres.user_store.get_session_factory", lambda: factory)
        return PostgresUserStore()

    def test_create_and_get_user(self, tmp_path, monkeypatch):
        store = self._store(tmp_path, monkeypatch)
        created = store.create_user("admin", "pass123", [UserRole.admin, UserRole.auditor])

        loaded = store.get_user_by_username("admin")

        assert loaded is not None
        assert loaded.user_id == created.user_id
        assert loaded.username == "admin"
        assert loaded.roles == [UserRole.admin, UserRole.auditor]

    def test_duplicate_user_raises(self, tmp_path, monkeypatch):
        store = self._store(tmp_path, monkeypatch)
        store.create_user("admin", "pass123", [UserRole.admin])

        try:
            store.create_user("admin", "other", [UserRole.viewer])
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_authenticate_user(self, tmp_path, monkeypatch):
        store = self._store(tmp_path, monkeypatch)
        store.create_user("admin", "pass123", [UserRole.admin])

        assert store.authenticate_user("admin", "pass123") is not None
        assert store.authenticate_user("admin", "wrong") is None
        assert store.authenticate_user("nobody", "pass123") is None

    def test_disabled_user_cannot_authenticate(self, tmp_path, monkeypatch):
        store = self._store(tmp_path, monkeypatch)
        store.create_user("viewer", "pass123", [UserRole.viewer], disabled=True)

        assert store.authenticate_user("viewer", "pass123") is None

    def test_seed_default_admin_if_empty(self, tmp_path, monkeypatch):
        store = self._store(tmp_path, monkeypatch)
        store.seed_default_admin_if_empty()

        assert store.get_user_by_username("admin") is not None
        assert store.get_user_by_username("operator") is not None
        assert store.get_user_by_username("viewer") is not None
        assert store.get_user_by_username("auditor") is not None

    def test_seed_default_admin_does_not_overwrite_existing_users(self, tmp_path, monkeypatch):
        store = self._store(tmp_path, monkeypatch)
        store.create_user("custom", "pass123", [UserRole.viewer])

        store.seed_default_admin_if_empty()

        assert store.get_user_by_username("custom") is not None
        assert store.get_user_by_username("admin") is None


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
