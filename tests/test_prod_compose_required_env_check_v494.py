from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.prod_compose_required_env_check import build_prod_compose_required_env_check


def _write_compose(root: Path, prod_text: str) -> None:
    (root / "docker-compose.yml").write_text("services:\n  app:\n    image: app\n", encoding="utf-8")
    (root / "docker-compose.prod.yml").write_text(prod_text, encoding="utf-8")


def test_prod_compose_required_env_check_passes_when_required_keys_fail_closed(
    tmp_path: Path, monkeypatch
) -> None:
    _write_compose(
        tmp_path,
        """
services:
  app:
    environment:
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}
      REDIS_URL: ${REDIS_URL:?REDIS_URL is required}
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET is required}
""".strip(),
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr=(
                "error while interpolating services.app.environment.DATABASE_URL: "
                "required variable DATABASE_URL is missing a value: DATABASE_URL is required"
            ),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://agent:secret@host/db")
    monkeypatch.setenv("REDIS_URL", "redis://:secret@redis:6379/0")
    monkeypatch.setenv("JWT_SECRET", "secret-value-before-check")

    payload = build_prod_compose_required_env_check(root_dir=tmp_path)

    assert payload["status"] == "success"
    assert payload["compose_executed"] is True
    assert payload["compose_return_code"] == 1
    assert payload["missing_conditions"] == []
    assert payload["env_restored"] is True
    assert os.environ["DATABASE_URL"] == "postgresql+psycopg://agent:secret@host/db"
    assert os.environ["REDIS_URL"] == "redis://:secret@redis:6379/0"
    assert os.environ["JWT_SECRET"] == "secret-value-before-check"


def test_prod_compose_required_env_check_blocks_if_compose_succeeds_without_env(
    tmp_path: Path, monkeypatch
) -> None:
    _write_compose(
        tmp_path,
        """
services:
  app:
    environment:
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}
      REDIS_URL: ${REDIS_URL:?REDIS_URL is required}
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET is required}
""".strip(),
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="services: {}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    payload = build_prod_compose_required_env_check(root_dir=tmp_path)

    assert payload["status"] == "blocked"
    assert "compose:prod_config_succeeded_without_required_env" in payload["missing_conditions"]


def test_prod_compose_required_env_check_blocks_unrelated_compose_failure(
    tmp_path: Path, monkeypatch
) -> None:
    _write_compose(
        tmp_path,
        """
services:
  app:
    environment:
      DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}
      REDIS_URL: ${REDIS_URL:?REDIS_URL is required}
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET is required}
""".strip(),
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr="yaml: line 2: mapping values are not allowed in this context",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    payload = build_prod_compose_required_env_check(root_dir=tmp_path)

    assert payload["status"] == "blocked"
    assert "compose:prod_config_failed_without_required_env_error" in payload["missing_conditions"]


def test_prod_compose_required_env_check_blocks_missing_required_interpolation(tmp_path: Path) -> None:
    _write_compose(
        tmp_path,
        """
services:
  app:
    environment:
      DATABASE_URL: ${DATABASE_URL:-}
      REDIS_URL: ${REDIS_URL:?REDIS_URL is required}
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET is required}
""".strip(),
    )

    payload = build_prod_compose_required_env_check(root_dir=tmp_path, execute=False)

    assert payload["status"] == "blocked"
    assert payload["compose_executed"] is False
    assert "compose:DATABASE_URL_required_interpolation_missing" in payload["missing_conditions"]
