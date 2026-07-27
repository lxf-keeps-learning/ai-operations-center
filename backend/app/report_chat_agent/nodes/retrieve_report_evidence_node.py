"""按问题意图提取当前报告内的结构化事实与稳定证据引用。"""

from __future__ import annotations

import json
from typing import Any

from app.report_chat_agent.state import ReportChatState


def retrieve_report_evidence_node(state: ReportChatState) -> ReportChatState:
    q = state.get("user_question", "").strip().lower()
    retrieved: list[dict[str, Any]] = []
    evidence_refs: list[str] = []

    def append_items(kind: str, items: list[dict], default_title: str) -> None:
        for item in items:
            refs = _extract_evidence_refs(item)
            retrieved.append({
                "type": kind,
                "title": _item_title(item, default_title),
                "content": _item_content(item),
                "evidence_refs": refs,
            })
            evidence_refs.extend(refs)

    if any(kw in q for kw in ("风险", "排序", "排第", "优先级", "严重")):
        append_items("risk_item", state.get("risk_items", []), "风险项")

    if any(kw in q for kw in ("异常", "清单", "异常项", "隐患")):
        append_items("abnormal_item", state.get("abnormal_items", []), "异常项")

    if any(kw in q for kw in ("建议", "动作", "整改", "下一步", "处理")):
        append_items("advice_item", state.get("advice_items", []), "建议项")

    if any(kw in q for kw in ("指标", "正常", "阈值", "率", "数量", "多少")):
        append_items("metric", state.get("metrics", []), "指标")

    if any(kw in q for kw in ("工单", "隐患", "关联", "闭环", "告警")):
        for source_name, items in _raw_data_collections(state.get("raw_data", {})):
            append_items(f"raw_{source_name}", items, source_name)

    if any(kw in q for kw in ("原因", "为什么", "依据", "结论", "规则", "判断")):
        for section in state.get("report_sections", []):
            content = str(section.get("content", "")).strip()
            if content:
                retrieved.append({
                    "type": "report_section",
                    "title": section.get("title", ""),
                    "content": content[:800],
                    "evidence_refs": [],
                })
        basis = state.get("analysis_basis", {})
        if basis:
            retrieved.append({
                "type": "analysis_basis",
                "title": "分析依据、假设与待核验项",
                "content": json.dumps(basis, ensure_ascii=False, default=str),
                "evidence_refs": [],
            })
        append_items("evidence", state.get("evidence", []), "证据")

    if not retrieved:
        summary = str(state.get("report_context", {}).get("summary", "")).strip()
        if summary:
            retrieved.append({
                "type": "report_summary",
                "title": "报告摘要",
                "content": summary,
                "evidence_refs": [],
            })
        append_items("evidence", state.get("evidence", [])[:6], "证据")

    state["retrieved_context"] = retrieved
    state["evidence_refs"] = list(dict.fromkeys(ref for ref in evidence_refs if ref))
    return state


def _extract_evidence_refs(item: dict) -> list[str]:
    direct = item.get("evidence_id") or item.get("id")
    refs: list[str] = [str(direct)] if direct else []
    nested = item.get("evidence_refs", []) or item.get("evidence", [])
    if isinstance(nested, list):
        for value in nested:
            if isinstance(value, dict):
                ref = value.get("evidence_id") or value.get("id") or value.get("record_id")
            else:
                ref = value
            if ref:
                refs.append(str(ref))
    return list(dict.fromkeys(refs))


def _item_title(item: dict, default: str) -> str:
    for key in ("title", "risk_name", "metric_name", "name", "description"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    return default


def _item_content(item: dict) -> str:
    return json.dumps(item, ensure_ascii=False, default=str)


def _raw_data_collections(raw_data: dict) -> list[tuple[str, list[dict]]]:
    if not isinstance(raw_data, dict):
        return []
    output: list[tuple[str, list[dict]]] = []
    for key, value in raw_data.items():
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            output.append((str(key), value))
        elif isinstance(value, dict):
            items = value.get("items")
            if isinstance(items, list) and items and all(isinstance(item, dict) for item in items):
                output.append((str(key), items))
    return output
