"""内容审核器。

支持中英文敏感词匹配、脱敏、拦截。
使用 Trie 树实现高效多模式匹配。
"""

import re
from dataclasses import dataclass, field
from typing import ClassVar

from app.security.constants import ModerationAction, ModerationSeverity
from app.security.sensitive_data import scan_sensitive_data
from app.security.sensitive_words import SENSITIVE_WORDS


@dataclass
class ModerationResult:
    action: ModerationAction = ModerationAction.PASS
    severity: ModerationSeverity | None = None
    matched_words: list[str] = field(default_factory=list)
    masked_text: str | None = None
    message: str | None = None
    sensitive_types: list[str] = field(default_factory=list)


class _TrieNode:
    __slots__ = ("children", "severity", "word")

    def __init__(self):
        self.children: dict[str, _TrieNode] = {}
        self.severity: ModerationSeverity | None = None
        self.word: str | None = None


class ContentModerator:
    _instance: ClassVar["ContentModerator | None"] = None

    def __init__(self):
        self._root = _TrieNode()
        self._load_words()
        self._low_pattern: re.Pattern | None = None

    @classmethod
    def get_instance(cls) -> "ContentModerator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_words(self) -> None:
        for severity, words in SENSITIVE_WORDS.items():
            for word in words:
                self._add_word(word.lower(), severity)

    def _add_word(self, word: str, severity: ModerationSeverity) -> None:
        node = self._root
        for char in word:
            if char not in node.children:
                node.children[char] = _TrieNode()
            node = node.children[char]
        node.severity = severity
        node.word = word

    def _search(self, text: str) -> list[tuple[str, int, int, ModerationSeverity]]:
        text_lower = text.lower()
        matches: list[tuple[str, int, int, ModerationSeverity]] = []
        for i in range(len(text_lower)):
            node = self._root
            for j in range(i, len(text_lower)):
                char = text_lower[j]
                if char not in node.children:
                    break
                node = node.children[char]
                if node.severity is not None:
                    matches.append((node.word, i, j + 1, node.severity))
        return matches

    def _merge_overlapping(
        self, matches: list[tuple[str, int, int, ModerationSeverity]]
    ) -> list[tuple[str, int, int, ModerationSeverity]]:
        if not matches:
            return []
        merged = [matches[0]]
        for m in matches[1:]:
            last = merged[-1]
            if m[1] <= last[2]:
                if m[3].value > last[3].value:
                    merged[-1] = m
            else:
                merged.append(m)
        return merged

    def moderate(self, text: str, context: str = "") -> ModerationResult:
        return self._moderate_text(text, is_output=False)

    def _moderate_text(self, text: str, *, is_output: bool) -> ModerationResult:
        if not text:
            return ModerationResult(masked_text=text)

        sensitive = scan_sensitive_data(text)
        safe_text = sensitive.masked_text
        merged = self._merge_overlapping(self._search(safe_text))
        matched_words = list(dict.fromkeys(m[0] for m in merged))
        max_severity = max(merged, key=lambda x: x[3].value)[3] if merged else None

        if sensitive.has_credentials:
            return ModerationResult(
                action=ModerationAction.BLOCK,
                severity=ModerationSeverity.HIGH,
                matched_words=matched_words,
                masked_text=safe_text,
                message=(
                    "AI 回答包含凭据类敏感信息，已被过滤。"
                    if is_output
                    else "检测到密码、密钥、令牌或数据库连接信息，已阻断处理。"
                ),
                sensitive_types=sensitive.sensitive_types,
            )

        if not merged and not sensitive.has_sensitive_data:
            return ModerationResult(masked_text=safe_text)

        if max_severity == ModerationSeverity.HIGH:
            return ModerationResult(
                action=ModerationAction.BLOCK,
                severity=max_severity,
                matched_words=matched_words,
                masked_text=safe_text,
                message=(
                    "AI 生成的回答包含不适当内容，已被过滤。请尝试重新提问。"
                    if is_output
                    else "您的问题包含严重违规内容，已被系统拦截。请遵守法律法规，文明提问。"
                ),
                sensitive_types=sensitive.sensitive_types,
            )

        if max_severity == ModerationSeverity.MEDIUM:
            return ModerationResult(
                action=ModerationAction.BLOCK,
                severity=max_severity,
                matched_words=matched_words,
                masked_text=safe_text,
                message=(
                    "AI 生成的回答包含不适当内容，已被过滤。请尝试重新提问。"
                    if is_output
                    else "请保持文明用语，您的输入包含不适当内容。"
                ),
                sensitive_types=sensitive.sensitive_types,
            )

        masked = list(safe_text)
        for _, start, end, _ in merged:
            for pos in range(start, end):
                if masked[pos] != "\n":
                    masked[pos] = "*"
        masked_text = "".join(masked)

        return ModerationResult(
            action=ModerationAction.MASK,
            severity=ModerationSeverity.LOW,
            matched_words=matched_words,
            masked_text=masked_text,
            message="敏感信息已自动脱敏。",
            sensitive_types=sensitive.sensitive_types,
        )

    def moderate_output(self, text: str) -> ModerationResult:
        return self._moderate_text(text, is_output=True)


content_moderator = ContentModerator.get_instance()
