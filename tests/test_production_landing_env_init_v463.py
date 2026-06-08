from __future__ import annotations

from pathlib import Path

from scripts.production_landing_env_init import build_production_landing_env_init


def test_production_landing_env_init_creates_local_env_without_real_secret(tmp_path: Path) -> None:
    env_path = tmp_path / "local" / "production_landing.staging.env"
    template_path = tmp_path / "local" / "production_landing.staging.env.template"

    summary = build_production_landing_env_init(env_path=env_path, template_path=template_path)
    text = env_path.read_text(encoding="utf-8")

    assert summary["env_file_present"] is True
    assert summary["env_file_created"] is True
    assert summary["env_file_existed_before"] is False
    assert summary["env_file_overwritten"] is False
    assert summary["contains_real_secret"] is False
    assert summary["secret_plaintext_output"] is False
    assert "REAL_LLM_MODEL=gpt-5.5" in text
    assert "REAL_LLM_BASE_URL=http://100.119.206.22:8300/v1" in text
    assert "REAL_LLM_API_KEY=<secret-managed-token>" in text
    assert "XIAOMI_LLM_API_KEY=<secret-managed-token>" not in text
    assert "DATABASE_URL=<secret-managed-url>" in text
    assert "REDIS_URL=<secret-managed-url>" in text
    assert "tp-" not in text
    assert "sk-" not in text
    assert summary["next_command"].startswith(
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\codex_python.ps1 "
    )
    assert "scripts\\production_landing_env_check.py" in summary["next_command"]
    assert not summary["next_command"].startswith("python scripts/")


def test_production_landing_env_init_does_not_overwrite_existing_env_by_default(tmp_path: Path) -> None:
    env_path = tmp_path / "local" / "production_landing.staging.env"
    template_path = tmp_path / "local" / "production_landing.staging.env.template"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("REAL_LLM_MODEL=custom\n", encoding="utf-8")

    summary = build_production_landing_env_init(env_path=env_path, template_path=template_path)

    assert summary["env_file_present"] is True
    assert summary["env_file_created"] is False
    assert summary["env_file_existed_before"] is True
    assert summary["env_file_overwritten"] is False
    assert env_path.read_text(encoding="utf-8") == "REAL_LLM_MODEL=custom\n"
