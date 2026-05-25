from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PIIFinding:
    type: str
    value: str
    masked_value: str
    risk_level: str
    start: int
    end: int


class PIIGuard:
    """PII 规则检测与脱敏器（规则型，不是完整 DLP）。"""

    _EMAIL = re.compile(r"\b([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]{0,30})@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
    _CN_MOBILE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
    _CN_ID = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
    _BANK_CARD = re.compile(r"(?<!\d)(\d{16,19})(?!\d)")
    _SK_KEY = re.compile(r"\b(sk-[A-Za-z0-9_-]{10,})\b")
    _BEARER = re.compile(r"\b(Bearer\s+[A-Za-z0-9._\-]{10,})\b", re.IGNORECASE)
    _LONG_SECRET = re.compile(r"\b([A-Za-z0-9_\-]{24,})\b")

    def detect(self, text: str) -> list[PIIFinding]:
        if not text:
            return []
        findings: list[PIIFinding] = []
        findings.extend(self._find_email(text))
        findings.extend(self._find_mobile(text))
        findings.extend(self._find_cn_id(text))
        findings.extend(self._find_bank_card(text))
        findings.extend(self._find_token_like(text))
        findings.sort(key=lambda x: (x.start, x.end))
        return findings

    def redact(self, text: str) -> tuple[str, list[PIIFinding]]:
        if not text:
            return text, []
        findings = self.detect(text)
        if not findings:
            return text, []

        pieces: list[str] = []
        cursor = 0
        filtered = self._dedup_overlap(findings)
        for f in filtered:
            if f.start > cursor:
                pieces.append(text[cursor:f.start])
            pieces.append(f.masked_value)
            cursor = f.end
        if cursor < len(text):
            pieces.append(text[cursor:])
        return "".join(pieces), filtered

    def _dedup_overlap(self, findings: list[PIIFinding]) -> list[PIIFinding]:
        result: list[PIIFinding] = []
        last_end = -1
        for f in findings:
            if f.start < last_end:
                continue
            result.append(f)
            last_end = f.end
        return result

    def _find_email(self, text: str) -> list[PIIFinding]:
        out: list[PIIFinding] = []
        for m in self._EMAIL.finditer(text):
            full = m.group(0)
            local_first = m.group(1)
            domain = m.group(3)
            masked = f"{local_first}***@{domain}"
            out.append(PIIFinding("email", full, masked, "medium", m.start(), m.end()))
        return out

    def _find_mobile(self, text: str) -> list[PIIFinding]:
        out: list[PIIFinding] = []
        for m in self._CN_MOBILE.finditer(text):
            full = m.group(1)
            masked = f"{full[:3]}****{full[-4:]}"
            out.append(PIIFinding("mobile_cn", full, masked, "high", m.start(1), m.end(1)))
        return out

    def _find_cn_id(self, text: str) -> list[PIIFinding]:
        out: list[PIIFinding] = []
        for m in self._CN_ID.finditer(text):
            full = m.group(1)
            masked = f"{full[:3]}{'*' * (len(full) - 5)}{full[-2:]}"
            out.append(PIIFinding("id_cn", full, masked, "high", m.start(1), m.end(1)))
        return out

    def _find_bank_card(self, text: str) -> list[PIIFinding]:
        out: list[PIIFinding] = []
        for m in self._BANK_CARD.finditer(text):
            full = m.group(1)
            if full.startswith("1") and len(full) == 18:
                continue
            masked = f"{full[:4]}{'*' * (len(full) - 8)}{full[-4:]}"
            out.append(PIIFinding("bank_card", full, masked, "high", m.start(1), m.end(1)))
        return out

    def _find_token_like(self, text: str) -> list[PIIFinding]:
        out: list[PIIFinding] = []
        out.extend(self._find_regex_token(text, self._SK_KEY, "api_key", "high"))
        out.extend(self._find_regex_token(text, self._BEARER, "bearer_token", "high"))
        for m in self._LONG_SECRET.finditer(text):
            full = m.group(1)
            if full.lower().startswith(("http", "select", "insert", "delete", "update")):
                continue
            masked = self._mask_secret(full)
            out.append(PIIFinding("secret_like", full, masked, "medium", m.start(1), m.end(1)))
        return out

    def _find_regex_token(self, text: str, pattern: re.Pattern[str], t: str, level: str) -> list[PIIFinding]:
        out: list[PIIFinding] = []
        for m in pattern.finditer(text):
            full = m.group(1)
            out.append(PIIFinding(t, full, self._mask_secret(full), level, m.start(1), m.end(1)))
        return out

    @staticmethod
    def _mask_secret(value: str) -> str:
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
