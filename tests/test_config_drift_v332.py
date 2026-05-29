from __future__ import annotations

import json
from pathlib import Path

import scripts.config_drift_check as config_drift


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_config_drift_generates_json_and_markdown(tmp_path: Path, monkeypatch):
    env_example = tmp_path / ".env.example"
    env_prod = tmp_path / ".env.production.example"
    _write(
        env_example,
        "APP_ENV=development\nJWT_SECRET=dev-only\nDATABASE_URL=\nREDIS_URL=redis://localhost:6379/0\n",
    )
    _write(
        env_prod,
        "APP_ENV=production\nJWT_SECRET=<replace>\nDATABASE_URL=postgres://placeholder\nREDIS_URL=redis://placeholder\n",
    )

    monkeypatch.setattr(config_drift, "ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setattr(config_drift, "ENV_PRODUCTION_EXAMPLE_PATH", env_prod)

    summary = config_drift.build_config_drift_report(output_dir=tmp_path / "out")
    json_path = Path(summary["json_path"])
    markdown_path = Path(summary["markdown_path"])

    assert summary["status"] == "ok"
    assert json_path.exists()
    assert markdown_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["generated_at"]
    assert payload["commit"]
    assert "checked_files" in payload
    assert "compose_required_env" in payload
    assert "boundary_declarations" in payload


def test_config_drift_read_only_no_file_mutation(tmp_path: Path, monkeypatch):
    env_example = tmp_path / ".env.example"
    env_prod = tmp_path / ".env.production.example"
    example_content = "APP_ENV=development\nJWT_SECRET=dev\n"
    prod_content = "APP_ENV=production\nJWT_SECRET=<replace>\nDATABASE_URL=<replace>\nREDIS_URL=<replace>\n"
    _write(env_example, example_content)
    _write(env_prod, prod_content)

    monkeypatch.setattr(config_drift, "ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setattr(config_drift, "ENV_PRODUCTION_EXAMPLE_PATH", env_prod)

    config_drift.build_config_drift_report(output_dir=tmp_path / "out")

    assert env_example.read_text(encoding="utf-8") == example_content
    assert env_prod.read_text(encoding="utf-8") == prod_content


def test_config_drift_missing_keys_are_warnings(tmp_path: Path, monkeypatch):
    env_example = tmp_path / ".env.example"
    env_prod = tmp_path / ".env.production.example"
    _write(env_example, "APP_ENV=development\nJWT_SECRET=dev\n")
    _write(env_prod, "APP_ENV=production\nJWT_SECRET=<replace>\nDATABASE_URL=<replace>\nREDIS_URL=<replace>\n")

    monkeypatch.setattr(config_drift, "ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setattr(config_drift, "ENV_PRODUCTION_EXAMPLE_PATH", env_prod)

    summary = config_drift.build_config_drift_report(output_dir=tmp_path / "out")
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))

    assert "DATABASE_URL" in payload["missing_in_example"]
    assert "REDIS_URL" in payload["missing_in_example"]
    assert payload["warnings"]
    assert any("missing" in warning.lower() for warning in payload["warnings"])


def test_config_drift_does_not_output_secret_values(tmp_path: Path, monkeypatch):
    env_example = tmp_path / ".env.example"
    env_prod = tmp_path / ".env.production.example"
    _write(
        env_example,
        "JWT_SECRET=placeholder-jwt-secret-example\nDATABASE_URL=postgresql://user:placeholder-pass@db:5432/app\nREDIS_URL=redis://:placeholder-redis-pass@redis:6379/0\n",
    )
    _write(
        env_prod,
        "JWT_SECRET=placeholder-jwt-secret-prod\nDATABASE_URL=postgresql://agent:placeholder-prod-pass@db:5432/app\nREDIS_URL=redis://:placeholder-prod-redis-pass@redis:6379/0\n",
    )

    monkeypatch.setattr(config_drift, "ENV_EXAMPLE_PATH", env_example)
    monkeypatch.setattr(config_drift, "ENV_PRODUCTION_EXAMPLE_PATH", env_prod)

    summary = config_drift.build_config_drift_report(output_dir=tmp_path / "out")
    merged = (
        Path(summary["json_path"]).read_text(encoding="utf-8")
        + "\n"
        + Path(summary["markdown_path"]).read_text(encoding="utf-8")
    )

    assert "placeholder-jwt-secret-example" not in merged
    assert "placeholder-jwt-secret-prod" not in merged
    assert "postgresql://user:placeholder-pass@" not in merged
    assert "postgresql://agent:placeholder-prod-pass@" not in merged
    assert "redis://:placeholder-redis-pass@" not in merged
    assert "redis://:placeholder-prod-redis-pass@" not in merged
