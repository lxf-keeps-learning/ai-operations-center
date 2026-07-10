"""内容审核器。

支持中英文敏感词匹配、脱敏、拦截。
使用 Trie 树实现高效多模式匹配。
"""

import re
from dataclasses import dataclass, field
from typing import ClassVar

from app.security.constants import ModerationAction, ModerationSeverity
from app.security.sensitive_words import SENSITIVE_WORDS


@dataclass
class ModerationResult:
    action: ModerationAction = ModerationAction.PASS
    severity: ModerationSeverity | None = None
    matched_words: list[str] = field(default_factory=list)
    masked_text: str | None = None
    message: str | None = None


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
        if not text:
            return ModerationResult()

        raw_matches = self._search(text)
        if not raw_matches:
            return ModerationResult()

        merged = self._merge_overlapping(raw_matches)
        matched_words = list(dict.fromkeys(m[0] for m in merged))
        max_severity = max(merged, key=lambda x: x[3].value)[3]

        if max_severity == ModerationSeverity.HIGH:
            return ModerationResult(
                action=ModerationAction.BLOCK,
                severity=max_severity,
                matched_words=matched_words,
                message="您的问题包含严重违规内容，已被系统拦截。请遵守法律法规，文明提问。",
            )

        if max_severity == ModerationSeverity.MEDIUM:
            return ModerationResult(
                action=ModerationAction.BLOCK,
                severity=max_severity,
                matched_words=matched_words,
                message="请保持文明用语，您的输入包含不适当内容。",
            )

        masked = list(text)
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
            message="输入内容已自动脱敏。",
        )

    def moderate_output(self, text: str) -> ModerationResult:
        if not text:
            return ModerationResult()

        raw_matches = self._search(text)
        if not raw_matches:
            return ModerationResult()

        merged = self._merge_overlapping(raw_matches)
        matched_words = list(dict.fromkeys(m[0] for m in merged))
        max_severity = max(merged, key=lambda x: x[3].value)[3]

        if max_severity in (ModerationSeverity.MEDIUM, ModerationSeverity.HIGH):
            return ModerationResult(
                action=ModerationAction.BLOCK,
                severity=max_severity,
                matched_words=matched_words,
                message="AI 生成的回答包含不适当内容，已被过滤。请尝试重新提问。",
            )

        masked = list(text)
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
        )


content_moderator = ContentModerator.get_instance()
