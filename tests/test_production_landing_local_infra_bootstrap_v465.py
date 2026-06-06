from __future__ import annotations

import json
from pathlib import Path

from scripts.production_landing_local_infra_bootstrap import build_production_landing_local_infra_bootstrap


def test_local_infra_bootstrap_writes_postgres_redis_values_without_summary_leak(tmp_path: Path) -> None:
    env_path = tmp_path / "local" / "production_landing.staging.env"

    summary = build_production_landing_local_infra_bootstrap(env_path=env_path)
    text = json.dumps(summary, ensure_ascii=False)
    env_text = env_path.read_text(encoding="utf-8")

    assert summary["env_file_present"] is True
    assert "DATABASE_URL" in summary["updated_secret_value_keys"]
    assert "REDIS_URL" in summary["updated_secret_value_keys"]
    assert summary["postgres_local_compose_ready"] is True
    assert summary["redis_local_compose_ready"] is True
    assert "docker compose up -d postgres redis" in summary["next_commands"]
    assert "DATABASE_URL=postgresql+psycopg://agent:dev-only-password@localhost:5432/project_b" in env_text
    assert "REDIS_URL=redis://localhost:6379/0" in env_text
    assert "postgresql+psycopg://agent:dev-only-password@localhost:5432/project_b" not in text
    assert "redis://localhost:6379/0" not in text
    assert summary["secret_plaintext_output"] is False


def test_local_infra_bootstrap_does_not_overwrite_existing_secret_values_by_default(tmp_path: Path) -> None:
    env_path = tmp_path / "local" / "production_landing.staging.env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://existing:secret@db/project_b",
                "REDIS_URL=redis://:existing-secret@redis:6379/0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = build_production_landing_local_infra_bootstrap(env_path=env_path)
    env_text = env_path.read_text(encoding="utf-8")

    assert summary["skipped_existing_secret_value_keys"] == ["DATABASE_URL", "REDIS_URL"]
    assert "DATABASE_URL" not in summary["updated_secret_value_keys"]
    assert "REDIS_URL" not in summary["updated_secret_value_keys"]
    assert "DATABASE_URL=postgresql://existing:secret@db/project_b" in env_text
    assert "REDIS_URL=redis://:existing-secret@redis:6379/0" in env_text


def test_local_infra_bootstrap_can_overwrite_existing_when_explicit(tmp_path: Path) -> None:
    env_path = tmp_path / "local" / "production_landing.staging.env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text(
        "DATABASE_URL=postgresql://existing:secret@db/project_b\nREDIS_URL=redis://:existing-secret@redis:6379/0\n",
        encoding="utf-8",
    )

    summary = build_production_landing_local_infra_bootstrap(env_path=env_path, overwrite_existing=True)
    env_text = env_path.read_text(encoding="utf-8")

    assert summary["skipped_existing_secret_value_keys"] == []
    assert "DATABASE_URL" in summary["updated_secret_value_keys"]
    assert "REDIS_URL" in summary["updated_secret_value_keys"]
    assert "DATABASE_URL=postgresql+psycopg://agent:dev-only-password@localhost:5432/project_b" in env_text
    assert "REDIS_URL=redis://localhost:6379/0" in env_text
