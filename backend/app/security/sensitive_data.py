"""输入输出中的敏感数据识别与不可逆脱敏。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SensitiveMatch:
    kind: str
    start: int
    end: int
    credential: bool = False


@dataclass(frozen=True)
class SensitiveScanResult:
    masked_text: str
    matches: tuple[SensitiveMatch, ...]

    @property
    def has_sensitive_data(self) -> bool:
        return bool(self.matches)

    @property
    def has_credentials(self) -> bool:
        return any(item.credential for item in self.matches)

    @property
    def sensitive_types(self) -> list[str]:
        return sorted({item.kind for item in self.matches})


_PATTERNS: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    ("database_url", re.compile(
        r"(?:mysql|postgres(?:ql)?|redis|mongodb)(?:\+[a-z0-9_]+)?://[^\s，。；,;]+",
        re.IGNORECASE,
    ), True),
    ("api_key", re.compile(
        r"(?:sk-|lsv2_)[A-Za-z0-9_-]{8,}\b",
        re.IGNORECASE,
    ), True),
    ("password", re.compile(
        r"(?:密码|password|passwd|pwd)\s*(?:是|为|=|:|：)?\s*[^\s，。；,;]+",
        re.IGNORECASE,
    ), True),
    ("access_token", re.compile(
        r"(?:token|bearer|访问令牌)\s*(?:是|为|=|:|：)?\s*[A-Za-z0-9._-]{8,}",
        re.IGNORECASE,
    ), True),
    ("cn_id_card", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), False),
    ("bank_card", re.compile(r"(?<!\d)\d{16,19}(?!\d)"), False),
    ("mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), False),
    ("email", re.compile(
        r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9.-])",
        re.IGNORECASE,
    ), False),
    ("address", re.compile(
        r"(?:家庭住址|居住地址|住址|(?<!数据库)地址)\s*(?:是|为|=|:|：)?\s*[^，。；,;\n]+"
    ), False),
    ("employee_id", re.compile(
        r"(?:员工号|工号)\s*(?:是|为|=|:|：)?\s*[A-Za-z0-9_-]+", re.IGNORECASE
    ), False),
    ("account", re.compile(
        r"(?:账号|用户名)\s*(?:是|为|=|:|：)?\s*[A-Za-z0-9_.@-]+", re.IGNORECASE
    ), False),
)


def scan_sensitive_data(text: str) -> SensitiveScanResult:
    """识别敏感片段，并用类型占位符替换，避免原文进入后续链路。"""

    candidates: list[tuple[int, SensitiveMatch]] = []
    for priority, (kind, pattern, credential) in enumerate(_PATTERNS):
        for match in pattern.finditer(text or ""):
            candidates.append((priority, SensitiveMatch(
                kind=kind,
                start=match.start(),
                end=match.end(),
                credential=credential,
            )))

    selected: list[SensitiveMatch] = []
    for _, candidate in sorted(
        candidates,
        key=lambda item: (item[1].start, item[0], -(item[1].end - item[1].start)),
    ):
        if any(candidate.start < current.end and candidate.end > current.start for current in selected):
            continue
        selected.append(candidate)

    masked_text = text or ""
    for item in sorted(selected, key=lambda value: value.start, reverse=True):
        masked_text = (
            masked_text[:item.start]
            + f"[REDACTED:{item.kind}]"
            + masked_text[item.end:]
        )

    return SensitiveScanResult(
        masked_text=masked_text,
        matches=tuple(sorted(selected, key=lambda value: value.start)),
    )
