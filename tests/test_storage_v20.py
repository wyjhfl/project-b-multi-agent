from __future__ import annotations

import os
from pathlib import Path


class TestStoreFactory:

    def test_sqlite_task_store_by_default(self):
        from app.storage.factory import get_task_store
        from app.storage.task_store import SQLiteTaskStore
        store = get_task_store()
        assert isinstance(store, SQLiteTaskStore)

    def test_sqlite_approval_store_by_default(self):
        from app.storage.factory import get_approval_store
        from app.storage.approval_store import SQLiteApprovalStore
        store = get_approval_store()
        assert isinstance(store, SQLiteApprovalStore)

    def test_sqlite_audit_store_by_default(self):
        from app.storage.factory import get_audit_store
        from app.storage.audit_store import SQLiteAuditStore
        store = get_audit_store()
        assert isinstance(store, SQLiteAuditStore)

    def test_sqlite_graph_checkpoint_store_by_default(self):
        from app.storage.factory import get_graph_checkpoint_store
        from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore
        store = get_graph_checkpoint_store()
        assert isinstance(store, SQLiteGraphCheckpointStore)


class TestMainStoreFactoryIntegration:

    def test_main_uses_sqlite_stores_by_default(self, monkeypatch):
        from app.core.config import settings
        import app.main as main
        from app.harness.metrics.metrics_store import SQLiteMetricsStore
        from app.storage.approval_store import SQLiteApprovalStore
        from app.storage.audit_store import SQLiteAuditStore
        from app.storage.task_store import SQLiteTaskStore

        monkeypatch.setattr(settings, "storage_backend", "sqlite")
        monkeypatch.setattr(settings, "database_url", "")
        main.reset_runtime_for_test()

        assert isinstance(main.get_task_store(), SQLiteTaskStore)
        assert isinstance(main.get_approval_store(), SQLiteApprovalStore)
        assert isinstance(main.get_audit_store(), SQLiteAuditStore)
        assert isinstance(main.get_metrics_store(), SQLiteMetricsStore)

        main.reset_runtime_for_test()

    def test_main_uses_postgres_stores_when_configured(self, monkeypatch):
        from app.core.config import settings
        import app.main as main
        from app.storage.postgres.approval_store import PostgresApprovalStore
        from app.storage.postgres.audit_store import PostgresAuditStore
        from app.storage.postgres.metrics_store import PostgresMetricsStore
        from app.storage.postgres.task_store import PostgresTaskStore

        monkeypatch.setattr(settings, "storage_backend", "postgres")
        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:pass@localhost:5432/project_b")
        main.reset_runtime_for_test()

        assert isinstance(main.get_task_store(), PostgresTaskStore)
        assert isinstance(main.get_approval_store(), PostgresApprovalStore)
        assert isinstance(main.get_audit_store(), PostgresAuditStore)
        assert isinstance(main.get_metrics_store(), PostgresMetricsStore)

        main.reset_runtime_for_test()

    def test_reset_runtime_recreates_store_from_current_config(self, monkeypatch):
        from app.core.config import settings
        import app.main as main
        from app.storage.postgres.task_store import PostgresTaskStore
        from app.storage.task_store import SQLiteTaskStore

        monkeypatch.setattr(settings, "storage_backend", "sqlite")
        monkeypatch.setattr(settings, "database_url", "")
        main.reset_runtime_for_test()
        first = main.get_task_store()
        assert isinstance(first, SQLiteTaskStore)

        monkeypatch.setattr(settings, "storage_backend", "postgres")
        monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:pass@localhost:5432/project_b")
        main.reset_runtime_for_test()
        second = main.get_task_store()
        assert isinstance(second, PostgresTaskStore)
        assert second is not first

        main.reset_runtime_for_test()


class TestAlembicMigration:

    def test_initial_migration_file_exists(self):
        path = Path(__file__).parent.parent / "alembic" / "versions" / "001_initial.py"
        assert path.exists()

    def test_alembic_ini_exists(self):
        path = Path(__file__).parent.parent / "alembic.ini"
        assert path.exists()

    def test_alembic_env_exists(self):
        path = Path(__file__).parent.parent / "alembic" / "env.py"
        assert path.exists()


class TestStorageModels:

    def test_user_row_tablename(self):
        from app.storage.models import UserRow
        assert UserRow.__tablename__ == "users"

    def test_task_run_row_tablename(self):
        from app.storage.models import TaskRunRow
        assert TaskRunRow.__tablename__ == "task_runs"

    def test_approval_request_row_tablename(self):
        from app.storage.models import ApprovalRequestRow
        assert ApprovalRequestRow.__tablename__ == "approval_requests"

    def test_audit_event_row_tablename(self):
        from app.storage.models import AuditEventRow
        assert AuditEventRow.__tablename__ == "audit_events"

    def test_runtime_task_metric_row_tablename(self):
        from app.storage.models import RuntimeTaskMetricRow
        assert RuntimeTaskMetricRow.__tablename__ == "runtime_task_metrics"

    def test_runtime_tool_metric_row_tablename(self):
        from app.storage.models import RuntimeToolMetricRow
        assert RuntimeToolMetricRow.__tablename__ == "runtime_tool_metrics"

    def test_runtime_token_usage_row_tablename(self):
        from app.storage.models import RuntimeTokenUsageRow
        assert RuntimeTokenUsageRow.__tablename__ == "runtime_token_usage"

    def test_graph_run_state_row_tablename(self):
        from app.storage.models import GraphRunStateRow
        assert GraphRunStateRow.__tablename__ == "graph_run_states"


class TestStoreProtocol:

    def test_sqlite_task_store_implements_protocol(self):
        from app.storage.base import TaskStoreProtocol
        from app.storage.task_store import SQLiteTaskStore
        assert isinstance(SQLiteTaskStore, TaskStoreProtocol)

    def test_sqlite_approval_store_implements_protocol(self):
        from app.storage.base import ApprovalStoreProtocol
        from app.storage.approval_store import SQLiteApprovalStore
        assert isinstance(SQLiteApprovalStore, ApprovalStoreProtocol)

    def test_sqlite_audit_store_implements_protocol(self):
        from app.storage.base import AuditStoreProtocol
        from app.storage.audit_store import SQLiteAuditStore
        assert isinstance(SQLiteAuditStore, AuditStoreProtocol)

    def test_sqlite_graph_checkpoint_store_implements_protocol(self):
        from app.storage.base import GraphCheckpointStoreProtocol
        from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore
        assert isinstance(SQLiteGraphCheckpointStore, GraphCheckpointStoreProtocol)


class TestDockerCompose:

    def test_docker_compose_file_exists(self):
        path = Path(__file__).parent.parent / "docker-compose.yml"
        assert path.exists()

    def test_docker_compose_contains_postgres(self):
        path = Path(__file__).parent.parent / "docker-compose.yml"
        content = path.read_text(encoding="utf-8")
        assert "postgres" in content

    def test_docker_compose_contains_redis(self):
        path = Path(__file__).parent.parent / "docker-compose.yml"
        content = path.read_text(encoding="utf-8")
        assert "redis" in content

    def test_docker_compose_app_depends_on_postgres(self):
        path = Path(__file__).parent.parent / "docker-compose.yml"
        content = path.read_text(encoding="utf-8")
        assert "DATABASE_URL" in content
        assert "REDIS_URL" in content


    def test_start_app_script_exists_and_runs_alembic(self):
        path = Path(__file__).parent.parent / "scripts" / "start_app.py"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "init_demo_db.py" in content
        assert "alembic" in content
        assert "upgrade" in content
        assert "head" in content

    def test_docker_startup_uses_start_app_script(self):
        root = Path(__file__).parent.parent
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
        assert "start_app.py" in dockerfile or "start_app.py" in compose

    def test_dockerfile_copies_alembic_files_for_startup_migration(self):
        path = Path(__file__).parent.parent / "Dockerfile"
        content = path.read_text(encoding="utf-8")
        assert "COPY alembic.ini" in content
        assert "COPY alembic/ alembic/" in content
        assert "start_app.py" in content
