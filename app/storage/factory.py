from __future__ import annotations

from app.core.config import settings


def get_task_store():
    if settings.storage_backend == "postgres" and settings.database_url:
        from app.storage.postgres.task_store import PostgresTaskStore
        return PostgresTaskStore()
    from app.storage.task_store import SQLiteTaskStore
    return SQLiteTaskStore()


def get_approval_store():
    if settings.storage_backend == "postgres" and settings.database_url:
        from app.storage.postgres.approval_store import PostgresApprovalStore
        return PostgresApprovalStore()
    from app.storage.approval_store import SQLiteApprovalStore
    return SQLiteApprovalStore()


def get_audit_store():
    if settings.storage_backend == "postgres" and settings.database_url:
        from app.storage.postgres.audit_store import PostgresAuditStore
        return PostgresAuditStore()
    from app.storage.audit_store import SQLiteAuditStore
    return SQLiteAuditStore()


def get_metrics_store():
    if settings.storage_backend == "postgres" and settings.database_url:
        from app.storage.postgres.metrics_store import PostgresMetricsStore
        return PostgresMetricsStore()
    from app.harness.metrics.metrics_store import SQLiteMetricsStore
    return SQLiteMetricsStore()

def get_graph_checkpoint_store():
    if settings.storage_backend == "postgres" and settings.database_url:
        from app.storage.postgres.graph_checkpoint_store import PostgresGraphCheckpointStore
        return PostgresGraphCheckpointStore()
    from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore
    return SQLiteGraphCheckpointStore()
