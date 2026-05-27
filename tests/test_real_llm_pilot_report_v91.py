from __future__ import annotations

import json
from datetime import datetime, timezone

from app.harness.llm.pilot_report import (
    REDACTED_PROMPT_PLACEHOLDER,
    PilotReportCase,
    build_pilot_report,
    sanitize_pilot_report_payload,
    summarize_base_url,
    write_pilot_report_json,
    write_pilot_report_markdown,
)


def _build_case(**overrides):
    payload = {
        "scenario": "nl2sql_preview_success",
        "endpoint": "/nl2sql/preview",
        "request_id": "req-v91",
        "provider": "litellm",
        "model": "gpt-4o-mini",
        "base_url_summary": summarize_base_url("https://api.openai.com/v1"),
        "api_key_env": "OPENAI_API_KEY",
        "api_key_present": True,
        "real_call_attempted": True,
        "real_call_succeeded": True,
        "fallback_used": False,
        "fallback_reason": "",
        "budget_action": "allow",
        "cache_hit": False,
        "latency_ms": 123.4,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "cost": 0.0123,
        "error_type": "",
        "outcome": "success",
        "warnings": [],
        "detail": {
            "query": "原始 query 文本",
            "messages": [{"role": "user", "content": "原始 prompt 文本"}],
            "token": "secret-token",
            "database_url": "postgresql://agent:db-password@localhost:5432/project_b",
            "redis_url": "redis://:redis-password@localhost:6379/0",
            "normal": "keep",
        },
    }
    payload.update(overrides)
    return PilotReportCase(**payload)


def test_schema_can_build_minimum_success_report():
    case = _build_case()
    report = build_pilot_report(
        cases=[case],
        commit="abc123",
        environment="test",
        report_id="pilot-v91",
        generated_at=datetime(2026, 5, 27, 8, 0, 0, tzinfo=timezone.utc),
    )
    payload = report.to_dict()
    assert payload["report_id"] == "pilot-v91"
    assert payload["provider"] == "litellm"
    assert payload["real_call_succeeded"] is True
    assert payload["cases"][0]["outcome"] == "success"


def test_failure_cases_can_be_recorded():
    fallback_case = _build_case(
        scenario="nl2sql_fallback",
        real_call_succeeded=False,
        fallback_used=True,
        fallback_reason="fallback_due_to_network_error",
        outcome="fallback",
        error_type="network_error",
    )
    budget_case = _build_case(
        scenario="budget_block",
        real_call_attempted=False,
        real_call_succeeded=False,
        fallback_used=True,
        fallback_reason="budget_blocked",
        budget_action="fallback",
        outcome="budget_block",
        error_type="budget_block",
    )
    auth_case = _build_case(
        scenario="auth_error",
        real_call_succeeded=False,
        fallback_used=False,
        fallback_reason="",
        outcome="auth_error",
        error_type="auth_error",
    )
    report = build_pilot_report(cases=[fallback_case, budget_case, auth_case], commit="abc", environment="dev")
    payload = report.to_dict()
    outcomes = [item["outcome"] for item in payload["cases"]]
    assert "fallback" in outcomes
    assert "budget_block" in outcomes
    assert "auth_error" in outcomes


def test_sanitize_payload_redacts_prompt_sensitive_and_dsn_password():
    raw = {
        "query": "原始 query 文本",
        "raw_prompt": "原始 prompt 文本",
        "input": "输入文本",
        "messages": [{"content": "message prompt"}],
        "token": "token-123",
        "openai_api_key": "sk-abc",
        "password": "db-pass",
        "authorization": "Bearer very-secret",
        "cookie": "a=1; b=2",
        "database_url": "postgresql://user:pass123@localhost:5432/db",
        "redis_url": "redis://:redispass@localhost:6379/0",
        "normal": "ok",
    }
    sanitized = sanitize_pilot_report_payload(raw)
    text = json.dumps(sanitized, ensure_ascii=False)
    assert REDACTED_PROMPT_PLACEHOLDER in text
    assert "原始 query 文本" not in text
    assert "原始 prompt 文本" not in text
    assert "message prompt" not in text
    assert "token-123" not in text
    assert "sk-abc" not in text
    assert "db-pass" not in text
    assert "very-secret" not in text
    assert "a=1; b=2" not in text
    assert "pass123" not in text
    assert "redispass" not in text
    assert sanitized["normal"] == "ok"


def test_base_url_summary_should_hide_path_query_and_userinfo():
    assert summarize_base_url("https://user:pass@api.example.com/v1/chat?x=1") == "https://api.example.com"
    assert summarize_base_url("") == "provider_default"


def test_write_json_and_markdown_should_succeed_with_tmp_path(tmp_path):
    case = _build_case()
    report = build_pilot_report(cases=[case], commit="abc123", environment="test", report_id="pilot-report")

    json_path = write_pilot_report_json(report, output_dir=tmp_path)
    md_path = write_pilot_report_markdown(report, output_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert json_path.parent == tmp_path
    assert md_path.parent == tmp_path


def test_json_markdown_should_not_contain_raw_prompt_or_secrets(tmp_path):
    case = _build_case(
        detail={
            "prompt": "原始 prompt 不能导出",
            "user_query": "原始 user_query 文本",
            "sql_prompt": "原始 sql_prompt 文本",
            "api_key": "sk-live-123",
            "secret": "secret-value",
            "authorization": "Bearer abc",
            "cookie": "sid=1",
            "database_url": "postgresql+psycopg://user:dbpassword@localhost:5432/db",
            "redis_url": "redis://:redis-password@localhost:6379/0",
        }
    )
    report = build_pilot_report(cases=[case], commit="abc", environment="test")
    json_path = write_pilot_report_json(report, output_dir=tmp_path)
    md_path = write_pilot_report_markdown(report, output_dir=tmp_path)

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")

    for text in (json_text, md_text):
        assert "原始 prompt 不能导出" not in text
        assert "原始 user_query 文本" not in text
        assert "原始 sql_prompt 文本" not in text
        assert "sk-live-123" not in text
        assert "secret-value" not in text
        assert "Bearer abc" not in text
        assert "sid=1" not in text
        assert "dbpassword" not in text
        assert "redis-password" not in text
        assert REDACTED_PROMPT_PLACEHOLDER in text


def test_markdown_should_include_controlled_pilot_boundary(tmp_path):
    case = _build_case()
    report = build_pilot_report(cases=[case], commit="abc", environment="test")
    md_path = write_pilot_report_markdown(report, output_dir=tmp_path)
    text = md_path.read_text(encoding="utf-8")
    assert "Controlled Pilot" in text
    assert "opt-in" in text
    assert "not production acceptance" in text
    assert "no raw prompt / no secrets" in text


def test_build_report_should_reject_empty_cases():
    try:
        build_pilot_report(cases=[], commit="abc", environment="test")
        raise AssertionError("应当抛出 ValueError")
    except ValueError as exc:
        assert "cases 不能为空" in str(exc)
