from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RiskIntentFinding:
    detected: bool
    reason: str = ""
    matched_keywords: list[str] = field(default_factory=list)


_RISK_INTENT_PATTERNS: list[tuple[str, str]] = [
    (r"删除", "删除操作"),
    (r"delete", "删除操作"),
    (r"drop", "删除操作"),
    (r"修改", "修改操作"),
    (r"update", "修改操作"),
    (r"alter", "修改操作"),
    (r"批量", "批量操作"),
    (r"batch", "批量操作"),
    (r"导出", "导出操作"),
    (r"export", "导出操作"),
    (r"绕过审批", "绕过审批"),
    (r"bypass\s+approval", "绕过审批"),
    (r"跳过审批", "绕过审批"),
    (r"直接执行", "直接执行"),
    (r"忽略.*指令", "忽略指令"),
    (r"ignore.*instruction", "忽略指令"),
    (r"系统密码", "系统密码"),
    (r"system\s+password", "系统密码"),
    (r"系统提示词", "提示词泄露"),
    (r"system\s+prompt", "提示词泄露"),
]


class RiskIntentGuard:
    def __init__(self) -> None:
        self._patterns = [(re.compile(p, re.IGNORECASE), label) for p, label in _RISK_INTENT_PATTERNS]

    def check(self, text: str) -> RiskIntentFinding:
        if not text:
            return RiskIntentFinding(detected=False)

        matched: list[str] = []
        for pattern, label in self._patterns:
            if pattern.search(text):
                matched.append(label)

        if matched:
            return RiskIntentFinding(
                detected=True,
                reason=f"检测到高风险意图: {', '.join(matched)}",
                matched_keywords=matched,
            )

        return RiskIntentFinding(detected=False)
