from __future__ import annotations

from pathlib import Path


def test_production_landing_signoff_closeout_ps1_requires_explicit_confirmations_without_plaintext_secret() -> None:
    text = Path("scripts/production_landing_signoff_closeout.ps1").read_text(encoding="utf-8")

    assert "production_landing_signoff_closeout.py" in text
    assert "Read-RequiredText" in text
    assert "Read-Confirmation" in text
    assert "Type YES to confirm" in text
    assert "--confirm-manual-signoff" in text
    assert "--confirm-controlled-pilot-go" in text
    assert "public production direct launch remains No-Go" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "CheckPythonOnly" in text
    assert "WindowsApps" in text
    assert "XDG_CONFIG_HOME" in text
    assert "PYTHONUTF8" in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "should-not-leak" not in text
