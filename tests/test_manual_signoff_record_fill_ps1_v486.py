from __future__ import annotations

from pathlib import Path


def test_manual_signoff_record_fill_ps1_requires_explicit_confirmations_without_plaintext_secret() -> None:
    text = Path("scripts/manual_signoff_record_fill.ps1").read_text(encoding="utf-8")

    assert "manual_signoff_record_fill.py" in text
    assert "Read-RequiredText" in text
    assert "Read-Confirmation" in text
    assert "Type YES to confirm" in text
    assert "--confirm-manual-signoff" in text
    assert "--confirm-controlled-pilot-go" in text
    assert "public production direct launch remains No-Go" in text
    assert "CheckPythonOnly" in text
    assert "WindowsApps" in text
    assert "codex安装" not in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "tp-" in text
    assert "sk-" in text
    assert "should-not-leak" not in text
