from __future__ import annotations

from pathlib import Path


def test_controlled_pilot_operator_packet_ps1_is_read_only_and_secret_safe() -> None:
    text = Path("scripts/controlled_pilot_operator_packet.ps1").read_text(encoding="utf-8")

    assert "do_not_enter_tokens_or_connection_strings=true" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "scripts\\codex_python.ps1" in text
    assert "controlled_pilot_status_summary.py" in text
    assert "controlled_pilot_operator_packet.py" in text
    assert "--output-dir" in text
    assert "Read-Host" not in text
    assert "-AsSecureString" not in text
    assert "SetEnvironmentVariable" not in text
    assert "WriteAllText" not in text
    assert ".env" not in text
    assert "tp-" not in text
    assert "sk-" not in text
