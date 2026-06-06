from __future__ import annotations

from app.core.config import Settings


class TestSettings:

    def test_default_values(self):
        s = Settings()
        assert s.database_url == ""
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.jwt_secret == "dev-only-change-me-please-32-bytes"
        assert len(s.jwt_secret) >= 32
        assert s.jwt_algorithm == "HS256"
        assert s.access_token_expire_minutes == 60
        assert s.auth_enabled is False
        assert s.rbac_enabled is False
        assert s.storage_backend == "sqlite"
        assert s.redis_enabled is False

    def test_database_url_empty_by_default(self):
        s = Settings()
        assert s.database_url == ""

    def test_storage_backend_sqlite_by_default(self):
        s = Settings()
        assert s.storage_backend == "sqlite"

    def test_auth_disabled_by_default(self):
        s = Settings()
        assert s.auth_enabled is False

    def test_rbac_disabled_by_default(self):
        s = Settings()
        assert s.rbac_enabled is False

    def test_redis_disabled_by_default(self):
        s = Settings()
        assert s.redis_enabled is False


class TestDatabase:

    def test_sqlite_engine_created(self):
        from app.storage.database import create_engine_from_settings, get_engine
        import app.storage.database as db_mod
        db_mod._engine = None
        db_mod._session_factory = None
        create_engine_from_settings()
        engine = get_engine()
        assert engine is not None
        assert "sqlite" in str(engine.url)

    def test_session_factory_created(self):
        from app.storage.database import create_engine_from_settings, get_session_factory
        import app.storage.database as db_mod
        db_mod._engine = None
        db_mod._session_factory = None
        create_engine_from_settings()
        factory = get_session_factory()
        assert factory is not None


class TestRedisClient:

    def test_noop_redis_when_disabled(self):
        from app.cache.redis_client import NoopRedisClient, get_redis_client
        import app.cache.redis_client as cache_mod
        cache_mod._redis_client = None
        client = get_redis_client()
        assert isinstance(client, NoopRedisClient)

    def test_noop_redis_get_returns_none(self):
        from app.cache.redis_client import NoopRedisClient
        client = NoopRedisClient()
        assert client.get("any_key") is None

    def test_noop_redis_set_no_error(self):
        from app.cache.redis_client import NoopRedisClient
        client = NoopRedisClient()
        client.set("key", "value")

    def test_noop_redis_ping_returns_false(self):
        from app.cache.redis_client import NoopRedisClient
        client = NoopRedisClient()
        assert client.ping() is False

    def test_noop_redis_exists_returns_false(self):
        from app.cache.redis_client import NoopRedisClient
        client = NoopRedisClient()
        assert client.exists("key") is False

    def test_check_redis_health_disabled(self):
        from app.cache.redis_client import check_redis_health
        result = check_redis_health()
        assert result["status"] == "disabled"
        assert result["backend"] == "noop"

    def test_check_redis_health_enabled_connection_failure_reports_error(self, monkeypatch):
        import app.cache.redis_client as cache_mod

        class FailingRedisLib:
            @staticmethod
            def from_url(*args, **kwargs):
                raise RuntimeError("connect failed")

        cache_mod.reset_redis_client()
        monkeypatch.setattr(cache_mod.settings, "redis_enabled", True)
        monkeypatch.setattr(cache_mod.settings, "redis_url", "redis://localhost:6379/0")
        monkeypatch.setitem(__import__("sys").modules, "redis", FailingRedisLib)

        result = cache_mod.check_redis_health()

        assert result["status"] == "error"
        assert result["backend"] == "redis"
        assert "error" in result
        cache_mod.reset_redis_client()
