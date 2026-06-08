from __future__ import annotations

from pathlib import Path

from scripts.production_landing_env_template import build_production_landing_env_template


def test_production_landing_env_template_writes_local_gitignored_template() -> None:
    summary = build_production_landing_env_template()
    path = Path(summary["template_path"])
    text = path.read_text(encoding="utf-8")

    assert summary["status"] == "success"
    assert summary["gitignored"] is True
    assert summary["secret_plaintext_output"] is False
    assert summary["contains_real_secret"] is False
    assert "REAL_LLM_MODEL=gpt-5.5" in text
    assert "REAL_LLM_BASE_URL=http://100.119.206.22:8300/v1" in text
    assert "REAL_LLM_API_KEY_ENV=REAL_LLM_API_KEY" in text
    assert "REAL_LLM_API_KEY=<secret-managed-token>" in text
    assert "DATABASE_URL=<secret-managed-url>" in text
    assert "REDIS_URL=<secret-managed-url>" in text
    assert "BUSINESS_SYSTEM_TOKEN=<secret-managed-token>" in text
    assert "BUSINESS_SYSTEM_AUTH_HEADER_NAME=Authorization" in text
    assert "BUSINESS_SYSTEM_AUTH_SCHEME=Bearer" in text
    assert "BUSINESS_SYSTEM_BUSINESS_OWNER=<owner-or-staff-id>" in text
    assert "BUSINESS_SYSTEM_SECURITY_REVIEWER=<owner-or-staff-id>" in text
    assert "BUSINESS_SYSTEM_OPERATIONS_OWNER=<owner-or-staff-id>" in text
    assert "BUSINESS_SYSTEM_DATA_OWNER=<owner-or-staff-id>" in text
    assert "scripts\\real_llm_preflight.ps1" in text
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains postgres" in text
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains redis" in text
    assert "scripts\\real_integration_infra_smoke.ps1 -Domains external_mcp" in text
    assert "scripts\\business_system_read_smoke.ps1" in text
    forbidden_real_key = "tp-" + "cfr5jno3cj4igfpe1p09gootwkb4w6atyl9n92zu0ep67xym"
    assert forbidden_real_key not in text
    assert "sk-" not in text
    assert "k-" not in text
    assert "bearer " not in text.lower()


def test_production_landing_env_template_custom_nonignored_path_reports_partial(tmp_path: Path) -> None:
    output = tmp_path / "landing.env.template"

    summary = build_production_landing_env_template(output_path=output)

    assert summary["status"] == "partial"
    assert summary["gitignored"] is False
    assert output.exists()
