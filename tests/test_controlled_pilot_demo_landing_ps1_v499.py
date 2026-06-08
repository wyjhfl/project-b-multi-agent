from __future__ import annotations

from pathlib import Path


def test_controlled_pilot_demo_landing_ps1_runs_demo_chain_without_real_business_secret() -> None:
    text = Path("scripts/controlled_pilot_demo_landing.ps1").read_text(encoding="utf-8")

    assert "controlled_pilot_demo_landing" in text
    assert "no_real_business_system=true" in text
    assert "do_not_enter_tokens_or_connection_strings=true" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "codex_python.ps1" in text
    assert "production_landing_demo_business_smoke.py" in text
    assert "business_system_landing_resume.ps1" in text
    assert "controlled_pilot_delivery_gate.py" in text
    assert "controlled_pilot_run_packet.py" in text
    assert "evidence_archive_manifest.py" in text
    assert "production_landing_text_quality_check.py" in text
    assert "$controlledInternalPilot" in text
    assert "$landingStatus" in text
    assert "$missingConditionCount" in text
    assert "missing_condition_count=$missingConditionCount" in text
    assert "missing_condition=" in text
    assert "controlled_internal_pilot=$controlledInternalPilot" in text
    assert "Get-JsonPathFromOutput" in text
    assert "BusinessReadSmokeJsonPath" in text
    assert "SkipBusinessPreparation" not in text
    assert "EnvPath" in text
    assert "controlled pilot run packet is not Go" not in text
    assert "Read-Host" not in text
    assert "-AsSecureString" not in text
    assert "SetEnvironmentVariable" not in text
    assert "WriteAllText" not in text
    assert "BUSINESS_SYSTEM_TOKEN" not in text
    assert "BUSINESS_SYSTEM_BASE_URL" not in text
    assert "tp-" not in text
    assert "sk-" not in text


def test_controlled_pilot_demo_landing_runbook_keeps_public_production_no_go_boundary() -> None:
    text = Path("docs/controlled_pilot_demo_landing_v49.md").read_text(encoding="utf-8")

    assert "没有真实业务系统" in text
    assert "demo read-only" in text
    assert "controlled internal pilot" in text
    assert "controlled_internal_pilot=Go" in text
    assert "controlled_internal_pilot=Manual-Review" in text
    assert "两种正常状态" in text
    assert "missing_condition_count" in text
    assert "missing_condition" in text
    assert "public_production_direct_launch=No-Go" in text
    assert "不等于真实业务系统生产验收完成" in text
    assert "business_system:real_business_system_required" in text
    assert "真实业务系统 base URL" in text
    assert "只读 token" in text
    assert "白名单" in text
    assert "审计" in text
    assert "回滚" in text
    assert "scripts\\controlled_pilot_demo_landing.ps1" in text
    assert "docs/reports/controlled_pilot_run_packet/" in text
    assert "docs/reports/evidence_archive/" in text
    assert "鐪熕疄" not in text
    assert "涓氬姟" not in text
    assert "鍙" not in text
    assert "tp-" not in text
    assert "sk-" not in text

def test_text_quality_default_targets_include_demo_landing_artifacts() -> None:
    import scripts.production_landing_text_quality_check as text_quality

    targets = {path.as_posix() for path in text_quality.DEFAULT_TARGETS}

    assert (text_quality.ROOT_DIR / "docs" / "controlled_pilot_demo_landing_v49.md").as_posix() in targets
    assert (text_quality.ROOT_DIR / "scripts" / "controlled_pilot_demo_landing.ps1").as_posix() in targets
