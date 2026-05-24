from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InjectionFinding:
    detected: bool
    severity: str
    reason: str
    matched_patterns: list[str] = field(default_factory=list)
    action: str = "allow"


_HIGH_BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"bypass\s+approval", "绕过审批"),
    (r"disable\s+policy", "关闭策略"),
    (r"approve\s+yourself", "自动批准"),
    (r"绕过审批", "绕过审批"),
    (r"自动批准", "自动批准"),
    (r"关闭策略", "关闭策略"),
    (r"直接调用工具", "直接调用工具"),
    (r"call\s+tool\s+directly", "直接调用工具"),
    (r"skip\s+validation", "跳过校验"),
    (r"drop\s+table", "删除表"),
    (r"delete\s+from", "删除数据"),
    (r"update\s+users", "修改用户数据"),
    (r"insert\s+into", "插入数据"),
    (r"删除表", "删除表"),
    (r"修改数据库", "修改数据库"),
]

_MEDIUM_BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"reveal\s+system\s+prompt", "泄露系统提示词"),
    (r"泄露系统提示词", "泄露系统提示词"),
    (r"show\s+system\s+prompt", "泄露系统提示词"),
    (r"ignore\s+previous\s+instructions?", "忽略之前的指令"),
    (r"ignore\s+above\s+instructions?", "忽略以上指令"),
    (r"忽略以上指令", "忽略以上指令"),
    (r"忽略之前的规则", "忽略之前的规则"),
]

_MEDIUM_WARN_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(rules?|instructions?|prompts?)", "模糊提示注入"),
    (r"forget\s+(all\s+)?(previous|prior|above)", "模糊提示注入"),
    (r"disregard\s+(all\s+)?(previous|prior|above)", "模糊提示注入"),
]


class PromptInjectionGuard:
    def __init__(self) -> None:
        self._high_block = [(re.compile(p, re.IGNORECASE), label) for p, label in _HIGH_BLOCK_PATTERNS]
        self._medium_block = [(re.compile(p, re.IGNORECASE), label) for p, label in _MEDIUM_BLOCK_PATTERNS]
        self._medium_warn = [(re.compile(p, re.IGNORECASE), label) for p, label in _MEDIUM_WARN_PATTERNS]

    def check_text(self, text: str) -> InjectionFinding:
        if not text:
            return InjectionFinding(detected=False, severity="low", reason="", action="allow")

        matched: list[str] = []

        for pattern, label in self._high_block:
            if pattern.search(text):
                matched.append(label)

        if matched:
            return InjectionFinding(
                detected=True,
                severity="high",
                reason=f"检测到高风险注入模式: {', '.join(matched)}",
                matched_patterns=matched,
                action="block",
            )

        for pattern, label in self._medium_block:
            if pattern.search(text):
                matched.append(label)

        if matched:
            return InjectionFinding(
                detected=True,
                severity="medium",
                reason=f"检测到提示注入模式: {', '.join(matched)}",
                matched_patterns=matched,
                action="block",
            )

        for pattern, label in self._medium_warn:
            if pattern.search(text):
                matched.append(label)

        if matched:
            return InjectionFinding(
                detected=True,
                severity="medium",
                reason=f"可能存在提示注入: {', '.join(matched)}",
                matched_patterns=matched,
                action="warn",
            )

        return InjectionFinding(detected=False, severity="low", reason="", action="allow")

    def check_payload(self, payload: dict) -> InjectionFinding:
        texts_to_check: list[str] = []
        self._collect_strings(payload, texts_to_check)

        worst: InjectionFinding | None = None

        for text in texts_to_check:
            finding = self.check_text(text)
            if finding.detected:
                if worst is None or (finding.action == "block" and worst.action != "block") or (finding.severity == "high" and worst.severity != "high"):
                    worst = finding

        return worst or InjectionFinding(detected=False, severity="low", reason="", action="allow")

    def _collect_strings(self, obj: Any, out: list[str]) -> None:
        if isinstance(obj, str) and obj:
            out.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._collect_strings(v, out)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._collect_strings(item, out)
