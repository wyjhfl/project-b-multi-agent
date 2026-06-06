from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.production_migration_drill import build_production_migration_drill


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_production_migration_drill_default_dry_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PRODUCTION_MIGRATION_DRILL_ENABLED", raising=False)
    summary = build_production_migration_drill(output_dir=tmp_path / "out")
    payload = _read_payload(summary)

    assert payload["status"] == "skipped"
    assert payload["migration_executed"] is False
    assert payload["database_connected"] is False
    assert payload["business_data_written"] is False
    assert payload["audit_data_written"] is False
    assert payload["metrics_data_written"] is False
    assert payload["secret_plaintext_output"] is False
    assert "cli:--execute_not_requested" in payload["missing_conditions"]


def test_production_migration_drill_execute_requires_opt_in(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PRODUCTION_MIGRATION_DRILL_ENABLED", raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    summary = build_production_migration_drill(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert payload["migration_executed"] is False
    assert "opt_in:PRODUCTION_MIGRATION_DRILL_ENABLED" in payload["missing_conditions"]


def test_production_migration_drill_sanitizes_command_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PRODUCTION_MIGRATION_DRILL_ENABLED", "true")
    monkeypatch.setenv("STORAGE_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db")

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="token=sk-sensitive-value", stderr="")

    summary = build_production_migration_drill(output_dir=tmp_path / "out", execute=True, command_runner=runner)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert "sk-sensitive-value" not in merged
    assert "[redacted-secret-like-text]" in merged
