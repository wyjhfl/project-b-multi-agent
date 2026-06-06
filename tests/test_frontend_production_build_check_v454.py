from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.frontend_production_build_check import build_frontend_production_build_check


def _read_payload(summary: dict) -> dict:
    return json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))


def test_frontend_production_build_check_default_skipped(tmp_path: Path) -> None:
    summary = build_frontend_production_build_check(output_dir=tmp_path / "out")
    payload = _read_payload(summary)
    markdown = Path(summary["markdown_path"]).read_text(encoding="utf-8")

    assert payload["status"] == "skipped"
    assert payload["execute"] is False
    assert payload["build_executed"] is False
    assert "cli:--execute_not_requested" in payload["missing_conditions"]
    assert payload["secret_plaintext_output"] is False
    assert summary["frontend_dir_present"] is True
    assert payload["build_command"] == "npm.cmd run build"
    assert "前端生产构建检查报告" in markdown
    assert "npm.cmd" in markdown
    assert "鍓嶇" not in markdown


def test_frontend_production_build_check_execute_success(tmp_path: Path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="Compiled successfully", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = build_frontend_production_build_check(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "success"
    assert payload["build_executed"] is True
    assert payload["return_code"] == 0
    assert payload["build_command"] == "npm.cmd run build"
    assert payload["frontend_dir_present"] is True
    assert payload["package_json_present"] is True
    assert payload["package_lock_present"] is True
    assert isinstance(payload["node_modules_present"], bool)
    assert payload["secret_plaintext_output"] is False
    assert "Compiled successfully" in merged or "Compiled successfully" in json.dumps(payload, ensure_ascii=False)


def test_frontend_production_build_check_redacts_secret_like_output(tmp_path: Path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="safe line\napi_key=sk-should-not-leak",
            stderr="Authorization: Bearer should-not-leak",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = build_frontend_production_build_check(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)
    merged = Path(summary["json_path"]).read_text(encoding="utf-8") + Path(summary["markdown_path"]).read_text(
        encoding="utf-8"
    )

    assert payload["status"] == "success"
    assert "[redacted-secret-like-build-line]" in merged
    assert "sk-should-not-leak" not in merged
    assert "should-not-leak" not in merged


def test_frontend_production_build_check_execute_failure(tmp_path: Path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="", stderr="Build failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    summary = build_frontend_production_build_check(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "failed"
    assert payload["build_executed"] is True
    assert payload["return_code"] == 1
    assert "Build failed" in json.dumps(payload, ensure_ascii=False)


def test_frontend_production_build_check_blocks_without_package_lock(tmp_path: Path, monkeypatch) -> None:
    import scripts.frontend_production_build_check as module

    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "FRONTEND_DIR", frontend)

    summary = module.build_frontend_production_build_check(output_dir=tmp_path / "out", execute=True)
    payload = _read_payload(summary)

    assert payload["status"] == "blocked"
    assert payload["build_executed"] is False
    assert "local:frontend_package_lock_missing" in payload["missing_conditions"]
