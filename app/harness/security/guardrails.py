from __future__ import annotations

from typing import Any, Literal

from app.agent.nl2sql.sql_guard import SQLGuard
from app.harness.security.injection_guard import PromptInjectionGuard
from app.harness.security.pii_guard import PIIFinding, PIIGuard

GuardAction = Literal["allow", "warn", "block", "redact"]
RiskLevel = Literal["low", "medium", "high"]


class GuardrailsEngine:
    """Guardrails 统一编排层（规则编排，不是黑箱安全模型）。"""

    _DANGEROUS_OUTPUT_RULES = [
        ("直接删除", "dangerous_delete_suggestion"),
        ("绕过审批", "bypass_approval_suggestion"),
        ("导出全部用户手机号", "bulk_pii_export_suggestion"),
        ("disable policy", "disable_policy_suggestion"),
        ("bypass approval", "bypass_approval_suggestion_en"),
        ("delete from", "dangerous_sql_suggestion_en"),
        ("drop table", "dangerous_ddl_suggestion_en"),
    ]

    def __init__(self) -> None:
        self._injection_guard = PromptInjectionGuard()
        self._sql_guard = SQLGuard()
        self._pii_guard = PIIGuard()

    def check_input(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        finding = self._injection_guard.check_text(text)
        pii_findings = self._pii_guard.detect(text)
        findings = []
        for p in pii_findings:
            findings.append(self._pii_to_dict(p))
        sanitized_text, _ = self._pii_guard.redact(text)

        if finding.action == "block":
            findings.append(
                {
                    "type": "prompt_injection",
                    "severity": finding.severity,
                    "reason": finding.reason,
                    "matched_patterns": finding.matched_patterns,
                }
            )
            return self._build_result(
                allowed=False,
                action="block",
                reason=finding.reason or "prompt injection blocked",
                findings=findings,
                sanitized_text=sanitized_text if pii_findings else None,
                risk_level="high",
            )

        if pii_findings:
            redacted, _ = self._pii_guard.redact(text)
            return self._build_result(
                allowed=True,
                action="warn",
                reason="PII detected in input",
                findings=findings,
                sanitized_text=redacted,
                risk_level="medium",
            )

        if finding.action == "warn":
            findings.append(
                {
                    "type": "prompt_injection_warn",
                    "severity": finding.severity,
                    "reason": finding.reason,
                    "matched_patterns": finding.matched_patterns,
                }
            )
            return self._build_result(
                allowed=True,
                action="warn",
                reason=finding.reason or "potential prompt injection",
                findings=findings,
                risk_level="medium",
            )

        return self._build_result(
            allowed=True,
            action="allow",
            reason="",
            findings=findings,
            risk_level="low",
        )

    def check_llm_output(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        risk_level: RiskLevel = "low"

        redacted_text, pii_findings = self._pii_guard.redact(text)
        for p in pii_findings:
            findings.append(self._pii_to_dict(p))
        action: GuardAction = "allow"
        reason = ""

        dangerous_rules_hit = []
        lowered = (text or "").lower()
        for rule, marker in self._DANGEROUS_OUTPUT_RULES:
            if rule.lower() in lowered:
                dangerous_rules_hit.append(marker)

        if dangerous_rules_hit:
            findings.append(
                {
                    "type": "dangerous_output_suggestion",
                    "matched_rules": dangerous_rules_hit,
                }
            )
            action = "warn"
            reason = "dangerous operation suggestion detected"
            risk_level = "high"

        if pii_findings:
            action = "redact" if action == "allow" else action
            if not reason:
                reason = "PII detected in LLM output"
            risk_level = "medium" if risk_level == "low" else risk_level

        return self._build_result(
            allowed=True,
            action=action,
            reason=reason,
            findings=findings,
            sanitized_text=redacted_text if pii_findings else None,
            risk_level=risk_level,
        )

    def check_sql(self, sql: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        guard_result = self._sql_guard.check(sql)
        if not guard_result.allowed:
            return self._build_result(
                allowed=False,
                action="block",
                reason=guard_result.reason,
                findings=[{"type": "sql_guard_blocked", "reason": guard_result.reason}],
                sanitized_text=guard_result.sql,
                risk_level="high",
            )
        return self._build_result(
            allowed=True,
            action="allow",
            reason="",
            findings=[],
            sanitized_text=guard_result.sql,
            risk_level="low",
        )

    def sanitize_response(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        redacted, findings = self._pii_guard.redact(text)
        if not findings:
            return self._build_result(
                allowed=True,
                action="allow",
                reason="",
                findings=[],
                sanitized_text=text,
                risk_level="low",
            )
        return self._build_result(
            allowed=True,
            action="redact",
            reason="response contains PII",
            findings=[self._pii_to_dict(f) for f in findings],
            sanitized_text=redacted,
            risk_level="medium",
        )

    def _pii_to_dict(self, finding: PIIFinding) -> dict[str, Any]:
        return {
            "type": finding.type,
            "value": finding.value,
            "masked_value": finding.masked_value,
            "risk_level": finding.risk_level,
            "span": [finding.start, finding.end],
        }

    @staticmethod
    def _build_result(
        *,
        allowed: bool,
        action: GuardAction,
        reason: str,
        findings: list[dict[str, Any]],
        sanitized_text: str | None = None,
        risk_level: RiskLevel = "low",
    ) -> dict[str, Any]:
        return {
            "allowed": allowed,
            "action": action,
            "reason": reason,
            "findings": findings,
            "sanitized_text": sanitized_text,
            "risk_level": risk_level,
        }
