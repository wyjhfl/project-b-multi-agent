from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    return cfg


def _table_columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    conn.close()
    return columns


def test_upgrade_head_adds_runtime_tool_metrics_status(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "migrate.sqlite"
    command.upgrade(_alembic_config(db_path), "head")
    assert "status" in _table_columns(db_path, "runtime_tool_metrics")


def test_orm_insert_matches_migrated_schema(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "migrate_orm.sqlite"
    command.upgrade(_alembic_config(db_path), "head")

    from app.storage.models import RuntimeToolMetricRow

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    with Session(engine) as session:
        session.add(
            RuntimeToolMetricRow(
                task_id="t-1",
                tool_name="demo_tool",
                status="success",
                success=1,
                latency_ms=1.2,
                retry_count=0,
            )
        )
        session.commit()
        row = session.query(RuntimeToolMetricRow).filter_by(task_id="t-1").one()
        assert row.status == "success"
    engine.dispose()


def test_downgrade_removes_status_column(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "migrate_down.sqlite"
    cfg = _alembic_config(db_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "002_graph_run_states")
    assert "status" not in _table_columns(db_path, "runtime_tool_metrics")
