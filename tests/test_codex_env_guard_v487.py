from __future__ import annotations

from pathlib import Path


def test_codex_env_guard_sets_stable_encoding_python_and_git_xdg() -> None:
    text = Path("scripts/codex_env_guard.ps1").read_text(encoding="utf-8")

    assert "chcp 65001" in text
    assert "InputEncoding" in text
    assert "OutputEncoding" in text
    assert "XDG_CONFIG_HOME" in text
    assert ".git-xdg" in text
    assert "PYTHONUTF8" in text
    assert "PYTHONIOENCODING" in text
    assert "ValueFromRemainingArguments" in text
    assert "PassthruArguments" in text
    assert "commandArguments" in text
    assert "WindowsApps" in text
    assert "D:\\codex*" in text
    assert "codex瀹夎" not in text
    assert "WriteAllText" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_gitignore_excludes_local_env_guard_state() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")

    assert ".git-xdg/" in text
    assert ".codex-env/" in text


def test_dedicated_codex_wrappers_cover_python_and_git_noise_sources() -> None:
    python_wrapper = Path("scripts/codex_python.ps1").read_text(encoding="utf-8")
    git_wrapper = Path("scripts/codex_git.ps1").read_text(encoding="utf-8")

    for text in [python_wrapper, git_wrapper]:
        assert "ValueFromRemainingArguments" in text
        assert "chcp 65001" in text
        assert "XDG_CONFIG_HOME" in text
        assert ".git-xdg" in text
        assert "tp-" not in text
        assert "sk-" not in text

    assert "WindowsApps" in python_wrapper
    assert "D:\\codex*" in python_wrapper
    assert "PYTHONUTF8" in python_wrapper
    assert "PYTHONIOENCODING" in python_wrapper


def test_windows_environment_guard_runbook_documents_stable_entrypoints() -> None:
    text = Path("docs/codex_windows_environment_guard_v48.md").read_text(encoding="utf-8")

    assert "Codex Windows 环境稳定执行规范" in text
    assert "scripts\\codex_python.ps1" in text
    assert "scripts\\codex_git.ps1" in text
    assert "Microsoft Store alias" in text
    assert "Windows PowerShell 5.1 默认文件读取编码不是 UTF-8" in text
    assert "Get-Content -LiteralPath 'docs\\reports\\example\\report.json' -Encoding UTF8 -Raw | ConvertFrom-Json" in text
    assert "XDG_CONFIG_HOME" in text
    assert ".git-xdg" in text
    assert "PYTHONUTF8" in text
    assert "Read-Host -AsSecureString" in text
    assert "public_production_direct_launch" in text
    assert "鐜" not in text
    assert "銆?" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_xiaomi_entrypoints_initialize_stable_process_environment() -> None:
    for path in [
        Path("scripts/xiaomi_llm_preflight.ps1"),
        Path("scripts/xiaomi_llm_landing_resume.ps1"),
    ]:
        text = path.read_text(encoding="utf-8")

        assert "Initialize-CodexProcessEnvironment" in text
        assert "chcp 65001" in text
        assert "InputEncoding" in text
        assert "OutputEncoding" in text
        assert "XDG_CONFIG_HOME" in text
        assert ".git-xdg" in text
        assert "PYTHONUTF8" in text
        assert "PYTHONIOENCODING" in text
        assert "tp-" not in text
        assert "sk-" not in text


def test_powershell_json_file_reads_use_explicit_utf8_encoding() -> None:
    for path in Path("scripts").glob("*.ps1"):
        text = path.read_text(encoding="utf-8")
        if "Get-Content" not in text or "ConvertFrom-Json" not in text:
            continue
        for line in text.splitlines():
            if "Get-Content" in line and "ConvertFrom-Json" in line:
                assert "-Encoding UTF8" in line, f"{path} should read JSON files as UTF-8: {line}"


def test_powershell_entrypoints_do_not_invoke_bare_python() -> None:
    offenders: list[str] = []

    for path in Path("scripts").glob("*.ps1"):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("python ") or stripped.startswith("python.exe "):
                offenders.append(f"{path}:{line_number}: {line}")
            if "& python" in line or "| python" in line:
                offenders.append(f"{path}:{line_number}: {line}")

    assert offenders == []


def test_operator_powershell_entrypoints_initialize_utf8_console() -> None:
    for path in [
        Path("scripts/demo_e2e.ps1"),
        Path("scripts/prod_config_check.ps1"),
        Path("scripts/real_llm_smoke.ps1"),
    ]:
        text = path.read_text(encoding="utf-8")

        assert "InputEncoding" in text
        assert "OutputEncoding" in text
        assert "chcp 65001" in text


def test_powershell_scripts_remain_windows_powershell_51_compatible() -> None:
    offenders: list[str] = []

    for path in Path("scripts").glob("*.ps1"):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "??" in line or "?." in line:
                offenders.append(f"{path}:{line_number}: {line}")

    assert offenders == []
