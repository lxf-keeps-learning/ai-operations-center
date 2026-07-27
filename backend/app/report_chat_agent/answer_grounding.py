"""报告问答生成后的轻量事实一致性校验。"""

from __future__ import annotations

import itertools
import json
import re
from typing import Any

from app.report_chat_agent.state import ReportChatState

_BUSINESS_ID = re.compile(
    r"\b(?:alarm|risk|wo|workorder|device|station)[-_][A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)


def validate_grounded_answer(answer: str, state: ReportChatState) -> list[str]:
    """拦截报告中不存在的业务 ID 和无依据的肯定关联。"""

    sources: list[Any] = [
        state.get("report_context", {}),
        state.get("metrics", []),
        state.get("abnormal_items", []),
        state.get("risk_items", []),
        state.get("advice_items", []),
        state.get("evidence", []),
        state.get("raw_data", {}),
        state.get("rag_results", []),
    ]
    source_text = json.dumps(sources, ensure_ascii=False, default=str)
    allowed_ids = {value.lower() for value in _BUSINESS_ID.findall(source_text)}
    answer_ids = {value.lower() for value in _BUSINESS_ID.findall(answer or "")}

    issues: list[str] = []
    unknown = sorted(answer_ids - allowed_ids)
    if unknown:
        issues.append(f"回答包含报告中不存在的业务 ID: {', '.join(unknown)}")

    for phrase in ("直接相关", "直接导致", "已确认原因为", "证明了"):
        if phrase in answer and phrase not in source_text:
            issues.append(f"回答把未确认的相关性表述为确定事实: {phrase}")

    open_ids = _collect_open_item_ids(sources)

    allowed_pairs = _collect_source_pairs(sources)
    for sentence in re.split(r"[。！？\n]", answer or ""):
        ids = sorted({value.lower() for value in _BUSINESS_ID.findall(sentence)})
        if (
            any(item_id in open_ids for item_id in ids)
            and any(word in sentence for word in ("实现闭环", "已闭环", "完成整改", "已完成整改"))
            and not any(word in sentence for word in ("未闭环", "尚未闭环", "未完成整改"))
        ):
            issues.append("回答把状态仍为 open/pending 的业务记录描述为已闭环")
        if len(ids) < 2:
            continue
        if not any(word in sentence for word in ("关联", "对应", "生成", "触发", "闭环")):
            continue
        if any(word in sentence for word in ("未发现", "没有", "无法确认", "不能确认", "无证据")):
            continue
        for pair in itertools.combinations(ids, 2):
            if tuple(sorted(pair)) not in allowed_pairs:
                issues.append(f"回答声明了报告数据未支持的关联: {pair[0]} / {pair[1]}")
    return list(dict.fromkeys(issues))


def grounding_fallback(state: ReportChatState) -> str:
    summary = str(state.get("report_context", {}).get("summary", "")).strip()
    lines = [
        "### 结论",
        "",
        "生成结果未通过事实一致性校验，因此不输出未经当前报告数据支持的确定性结论。",
    ]
    if summary:
        lines.extend(["", "### 当前报告可确认内容", "", summary[:500]])
    lines.extend([
        "",
        "### 建议",
        "",
        "请基于报告中的指标、异常项、工单和证据编号进一步核对；当前信息不足时应明确标记为待核验。",
    ])
    return "\n".join(lines)


def _collect_source_pairs(value: Any) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            ids = sorted({
                match.lower()
                for match in _BUSINESS_ID.findall(json.dumps(item, ensure_ascii=False, default=str))
            })
            pairs.update(tuple(sorted(pair)) for pair in itertools.combinations(ids, 2))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return pairs


def _collect_open_item_ids(value: Any) -> set[str]:
    output: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            status = str(item.get("status", "")).lower()
            if status in {"open", "pending", "processing", "unclosed"}:
                for candidate in item.values():
                    if isinstance(candidate, str) and _BUSINESS_ID.fullmatch(candidate):
                        output.add(candidate.lower())
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return output
