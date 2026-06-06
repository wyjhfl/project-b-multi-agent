from __future__ import annotations

import json
from pathlib import Path

from scripts.store_redis_readiness_drill import build_store_redis_readiness_drill


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def _clear_store_redis_env(monkeypatch) -> None:
    for key in ["STORAGE_BACKEND", "DATABASE_URL", "REDIS_ENABLED", "REDIS_URL", "JWT_SECRET"]:
        monkeypatch.delenv(key, raising=False)


def test_store_redis_readiness_drill_generates_outputs(tmp_path: Path, monkeypatch) -> None:
    _clear_store_redis_env(monkeypatch)
    summary = build_store_redis_readiness_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert summary["status"] == "skipped"
    assert summary["read_only"] is True
    assert summary["database_connected"] is False
    assert summary["redis_connected"] is False
    assert summary["migration_executed"] is False
    assert payload["version"] == "3.7.0"
    assert payload["phase"] == "v3.7 Phase 17.4"
    assert payload["check_count"] == len(payload["acceptance_checks"])
    assert Path(summary["markdown_path"]).exists()


def test_store_redis_readiness_drill_covers_required_checks(tmp_path: Path, monkeypatch) -> None:
    _clear_store_redis_env(monkeypatch)
    summary = build_store_redis_readiness_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    check_ids = {item["check_id"] for item in payload["acceptance_checks"]}

    assert {
        "postgres_store_opt_in_config",
        "store_factory_and_postgres_stores",
        "sqlite_default_fallback_preserved",
        "alembic_migration_precheck",
        "redis_opt_in_config",
        "noop_redis_fallback",
        "rate_limit_storage_boundary",
        "deployment_guard_store_redis_checks",
        "audit_metrics_store_boundary",
        "compose_readiness_files",
    } <= check_ids


def test_store_redis_readiness_drill_partial_when_opt_in_config_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "placeholder-not-a-url")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "placeholder-not-a-url")

    summary = build_store_redis_readiness_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "partial"
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
    assert payload["migration_executed"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False


def test_store_redis_readiness_drill_does_not_leak_secret_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:db-secret@localhost/db")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-secret@localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret-plain")

    summary = build_store_redis_readiness_drill(output_dir=tmp_path / "out")
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert "db-secret" not in merged
    assert "redis-secret" not in merged
    assert "jwt-secret-plain" not in merged
    assert "DATABASE_URL" in merged
    assert "REDIS_URL" in merged


def test_store_redis_readiness_drill_records_local_evidence_without_connections(tmp_path: Path, monkeypatch) -> None:
    _clear_store_redis_env(monkeypatch)
    summary = build_store_redis_readiness_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["local_checks"]["store_factory"]["present"] is True
    assert payload["local_checks"]["redis_client"]["present"] is True
    assert payload["alembic_migration_index"]["migration_executed"] is False
    assert payload["alembic_migration_index"]["migration_count"] >= 1
    rate_limit = next(item for item in payload["acceptance_checks"] if item["check_id"] == "rate_limit_storage_boundary")
    assert rate_limit["evidence"]["default_rate_limiter"] == "memory"
    assert rate_limit["evidence"]["redis_rate_limit_backend_available"] is True
    assert payload["database_connected"] is False
    assert payload["redis_connected"] is False
