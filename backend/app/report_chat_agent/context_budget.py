"""Report Chat Prompt 的确定性上下文预算与优先级裁剪。"""

import json
import math
from typing import Any

# 这是保守估算，不替代模型服务返回的真实 usage token。
CHARS_PER_ESTIMATED_TOKEN = 3


def estimate_tokens(text: str) -> int:
    return max(0, math.ceil(len(text.encode("utf-8")) / CHARS_PER_ESTIMATED_TOKEN))


def _serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _fit(value: Any, token_budget: int) -> tuple[str, bool, int]:
    text = _serialize(value)
    if estimate_tokens(text) <= token_budget:
        return text, False, estimate_tokens(text)
    max_chars = max(1, token_budget * CHARS_PER_ESTIMATED_TOKEN)
    clipped = text[:max_chars].rstrip() + "\n...[内容已按上下文预算裁剪]"
    while estimate_tokens(clipped) > token_budget and len(clipped) > 1:
        clipped = clipped[: max(1, len(clipped) - 10)]
    return clipped, True, estimate_tokens(clipped)


def build_context_budget(
    *,
    user_question: str,
    report_context: Any,
    evidence: Any,
    retrieved_context: Any,
    merged_context: Any,
    memory_context: Any,
    rag_results: Any,
    chat_history: Any,
    input_budget: int,
) -> dict[str, Any]:
    """按“问题 > 报告 > 证据 > 记忆 > RAG > 历史”顺序构造 Prompt 上下文。"""
    sections = [
        ("user_question", user_question, 300),
        ("report_context", report_context, 3500),
        ("evidence", evidence, 1800),
        ("retrieved_context", retrieved_context, 1000),
        ("merged_context", merged_context, 1000),
        ("memory_context", memory_context, 500),
        ("rag_results", rag_results, 800),
        ("chat_history", chat_history, 400),
    ]
    result: dict[str, Any] = {"contexts": [], "estimated_tokens": 0, "truncated": False}
    remaining = max(1, input_budget)
    for name, value, section_budget in sections:
        budget = min(section_budget, remaining)
        text, truncated, used = _fit(value, budget)
        result[name] = text
        result["contexts"].append(name)
        result["estimated_tokens"] += used
        result["truncated"] = result["truncated"] or truncated
        remaining = max(0, remaining - used)
        if remaining == 0:
            result["truncated"] = True
            for later_name, _, _ in sections[len(result["contexts"]):]:
                result[later_name] = ""
                result["contexts"].append(later_name)
            break
    return result
