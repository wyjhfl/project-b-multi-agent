from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest


def _make_sqlite_store(tmp_path):
    from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore

    return SQLiteGraphCheckpointStore(db_path=str(tmp_path / "checkpoint.sqlite"))


def test_sqlite_create_get_checkpoint(tmp_path):
    store = _make_sqlite_store(tmp_path)

    created = store.create_checkpoint(
        checkpoint_id="cp-1",
        task_id="task-1",
        graph_state={"step": 1, "nested": {"ok": True}},
        current_node="execute",
        graph_thread_id="thread-1",
        run_id="run-1",
    )
    loaded = store.get_checkpoint("cp-1")

    assert created["checkpoint_id"] == "cp-1"
    assert loaded is not None
    assert loaded["task_id"] == "task-1"
    assert loaded["graph_state"] == {"step": 1, "nested": {"ok": True}}
    assert loaded["current_node"] == "execute"
    assert loaded["graph_thread_id"] == "thread-1"
    assert loaded["run_id"] == "run-1"
    assert loaded["status"] == "running"
    assert loaded["consumed"] is False
    assert loaded["schema_version"] == 1
    assert loaded["resume_attempt_count"] == 0


def test_sqlite_duplicate_create_checkpoint_raises_value_error(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-dup", task_id="task-1", graph_state={"original": True})

    with pytest.raises(ValueError, match="cp-dup already exists"):
        store.create_checkpoint(checkpoint_id="cp-dup", task_id="task-2", graph_state={"replacement": True})


def test_sqlite_duplicate_create_does_not_overwrite_existing_consumed_checkpoint(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-dup", task_id="task-1", graph_state={"original": True})
    store.mark_cancelled("cp-dup", "already cancelled")

    with pytest.raises(ValueError, match="cp-dup already exists"):
        store.create_checkpoint(checkpoint_id="cp-dup", task_id="task-2", graph_state={"replacement": True})

    loaded = store.get_checkpoint("cp-dup")
    assert loaded is not None
    assert loaded["task_id"] == "task-1"
    assert loaded["graph_state"] == {"original": True}
    assert loaded["status"] == "cancelled"
    assert loaded["consumed"] is True


def test_postgres_create_checkpoint_source_has_no_existing_overwrite_logic():
    source = Path(__file__).parent.parent / "app" / "storage" / "postgres" / "graph_checkpoint_store.py"
    content = source.read_text(encoding="utf-8")

    create_section = content.split("    def get_checkpoint", 1)[0]
    assert "existing =" not in create_section
    assert "existing or GraphRunStateRow" not in create_section
    assert "already exists" in create_section


def test_sqlite_get_latest_for_task(tmp_path):
    store = _make_sqlite_store(tmp_path)
    old_time = datetime.now() - timedelta(minutes=5)
    new_time = datetime.now()

    store.create_checkpoint(checkpoint_id="old", task_id="task-1", graph_state={}, created_at=old_time)
    store.create_checkpoint(checkpoint_id="new", task_id="task-1", graph_state={}, created_at=new_time)

    latest = store.get_latest_for_task("task-1")

    assert latest is not None
    assert latest["checkpoint_id"] == "new"


def test_sqlite_mark_pending_interrupt(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-1", task_id="task-1", graph_state={"step": 1})

    updated = store.mark_pending_interrupt("cp-1", "apr-1", {"reason": "high risk", "tool": "danger"})

    assert updated is not None
    assert updated["status"] == "interrupted"
    assert updated["approval_id"] == "apr-1"
    assert updated["pending_interrupt"] == {"reason": "high risk", "tool": "danger"}
    assert updated["consumed"] is False


def test_sqlite_mark_pending_interrupt_can_update_graph_state(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-1", task_id="task-1", graph_state={"stage": "execute"})
    final_state = {
        "stage": "execute",
        "response": {"approval_id": "apr-1", "checkpoint_id": "cp-1", "graph_interrupt": True},
        "execution_result": {"approval_id": "apr-1"},
    }

    updated = store.mark_pending_interrupt("cp-1", "apr-1", {"reason": "high risk"}, graph_state=final_state)

    assert updated is not None
    assert updated["graph_state"] == final_state
    assert updated["graph_state"]["response"]["approval_id"] == "apr-1"


def test_sqlite_mark_pending_interrupt_without_graph_state_keeps_existing_graph_state(tmp_path):
    store = _make_sqlite_store(tmp_path)
    original_state = {"stage": "execute", "response": None}
    store.create_checkpoint(checkpoint_id="cp-1", task_id="task-1", graph_state=original_state)

    updated = store.mark_pending_interrupt("cp-1", "apr-1", {"reason": "high risk"})

    assert updated is not None
    assert updated["graph_state"] == original_state


def test_sqlite_claim_for_resume_first_success(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-1", task_id="task-1", graph_state={})
    store.mark_pending_interrupt("cp-1", "apr-1", {"reason": "high risk"})

    claimed = store.claim_for_resume("cp-1", "apr-1")

    assert claimed is not None
    assert claimed["checkpoint_id"] == "cp-1"
    assert claimed["status"] == "resuming"
    assert claimed["resume_attempt_count"] == 1
    assert claimed["locked_at"] is not None


def test_sqlite_claim_for_resume_second_denied(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-1", task_id="task-1", graph_state={})
    store.mark_pending_interrupt("cp-1", "apr-1", {"reason": "high risk"})

    first = store.claim_for_resume("cp-1", "apr-1")
    second = store.claim_for_resume("cp-1", "apr-1")

    assert first is not None
    assert second is None


def test_sqlite_expired_checkpoint_cannot_claim(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(
        checkpoint_id="cp-1",
        task_id="task-1",
        graph_state={},
        expires_at=datetime.now() - timedelta(seconds=1),
    )
    store.mark_pending_interrupt("cp-1", "apr-1", {"reason": "high risk"})

    claimed = store.claim_for_resume("cp-1", "apr-1")

    assert claimed is None


def test_sqlite_mark_resumed_sets_consumed_resumed_at_status(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-1", task_id="task-1", graph_state={})
    store.mark_pending_interrupt("cp-1", "apr-1", {"reason": "high risk"})
    store.claim_for_resume("cp-1", "apr-1")

    updated = store.mark_resumed("cp-1", {"decision": "approved"}, {"success": True})

    assert updated is not None
    assert updated["status"] == "resumed"
    assert updated["consumed"] is True
    assert updated["resumed_at"] is not None
    assert updated["resume_payload"] == {"decision": "approved"}
    assert updated["result_snapshot"] == {"success": True}


def test_sqlite_mark_cancelled_sets_consumed_status(tmp_path):
    store = _make_sqlite_store(tmp_path)
    store.create_checkpoint(checkpoint_id="cp-1", task_id="task-1", graph_state={})

    updated = store.mark_cancelled("cp-1", "rejected")

    assert updated is not None
    assert updated["status"] == "cancelled"
    assert updated["consumed"] is True
    assert updated["last_resume_error"] == "rejected"


def test_store_factory_default_returns_sqlite_checkpoint_store(monkeypatch):
    from app.core.config import settings
    from app.storage.factory import get_graph_checkpoint_store
    from app.storage.graph_checkpoint_store import SQLiteGraphCheckpointStore

    monkeypatch.setattr(settings, "storage_backend", "sqlite")
    monkeypatch.setattr(settings, "database_url", "")

    store = get_graph_checkpoint_store()

    assert isinstance(store, SQLiteGraphCheckpointStore)


def test_store_factory_postgres_config_returns_postgres_checkpoint_store(monkeypatch):
    from app.core.config import settings
    from app.storage.factory import get_graph_checkpoint_store
    from app.storage.postgres.graph_checkpoint_store import PostgresGraphCheckpointStore

    monkeypatch.setattr(settings, "storage_backend", "postgres")
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://user:pass@localhost:5432/project_b")

    store = get_graph_checkpoint_store()

    assert isinstance(store, PostgresGraphCheckpointStore)


def test_alembic_migration_contains_graph_run_states():
    path = Path(__file__).parent.parent / "alembic" / "versions" / "002_graph_run_states.py"

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "graph_run_states" in content
    assert "checkpoint_id" in content
    assert "pending_interrupt" in content
    assert "resume_payload" in content


def test_json_fields_round_trip_correctly(tmp_path):
    store = _make_sqlite_store(tmp_path)
    graph_state = {
        "messages": [{"role": "user", "content": "高风险审批"}],
        "numbers": [1, 2, 3],
        "none": None,
    }
    interrupt = {"risk_level": "high", "policy": {"requires_approval": True}}
    resume_payload = {"decision": "approved", "operator": "admin"}

    store.create_checkpoint(checkpoint_id="cp-json", task_id="task-json", graph_state=graph_state)
    store.mark_pending_interrupt("cp-json", "apr-json", interrupt)
    store.claim_for_resume("cp-json", "apr-json")
    store.mark_resumed("cp-json", resume_payload, {"ok": True})

    loaded = store.get_checkpoint("cp-json")

    assert loaded is not None
    assert loaded["graph_state"] == graph_state
    assert loaded["pending_interrupt"] == interrupt
    assert loaded["resume_payload"] == resume_payload
    assert loaded["result_snapshot"] == {"ok": True}
