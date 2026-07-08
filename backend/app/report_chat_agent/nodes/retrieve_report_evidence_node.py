from typing import Any

from app.report_chat_agent.state import ReportChatState


def retrieve_report_evidence_node(state: ReportChatState) -> ReportChatState:
    question = state.get("user_question", "")
    abnormal_items = state.get("abnormal_items", [])
    risk_items = state.get("risk_items", [])
    advice_items = state.get("advice_items", [])
    evidence = state.get("evidence", [])
    report_context = state.get("report_context", {})
    report_sections = state.get("report_sections", [])

    q = question.strip().lower()

    retrieved: list[dict[str, Any]] = []
    evidence_refs: list[str] = []

    if any(kw in q for kw in ["风险", "排序", "排第", "优先级"]):
        for item in risk_items:
            refs = _extract_evidence_refs(item)
            retrieved.append({
                "type": "risk_item",
                "title": item.get("title", "") or item.get("risk_name", "") or "风险项",
                "content": _item_content(item),
                "evidence_refs": refs,
            })
            evidence_refs.extend(refs)

    if any(kw in q for kw in ["异常", "清单", "严重", "异常项"]):
        for item in abnormal_items:
            refs = _extract_evidence_refs(item)
            retrieved.append({
                "type": "abnormal_item",
                "title": item.get("title", "") or item.get("metric_name", "") or "异常项",
                "content": _item_content(item),
                "evidence_refs": refs,
            })
            evidence_refs.extend(refs)

    if any(kw in q for kw in ["建议", "动作", "整改", "下一步"]):
        for item in advice_items:
            refs = _extract_evidence_refs(item)
            retrieved.append({
                "type": "advice_item",
                "title": item.get("title", "") or "建议项",
                "content": _item_content(item),
                "evidence_refs": refs,
            })
            evidence_refs.extend(refs)

    if any(kw in q for kw in ["原因", "为什么", "依据", "结论"]):
        for section in report_sections:
            retrieved.append({
                "type": "report_section",
                "title": section.get("title", ""),
                "content": section.get("content", "")[:500],
                "evidence_refs": [],
            })

        for ev in evidence:
            eid = ev.get("id", "") or ev.get("evidence_id", "") or ""
            retrieved.append({
                "type": "evidence",
                "title": ev.get("title", "") or ev.get("name", "") or "证据",
                "content": _item_content(ev),
                "evidence_refs": [eid] if eid else [],
            })
            if eid:
                evidence_refs.append(eid)

        if report_context:
            retrieved.append({
                "type": "report_summary",
                "title": "报告摘要",
                "content": report_context.get("summary", ""),
                "evidence_refs": [],
            })

    if not retrieved:
        retrieved.append({
            "type": "report_summary",
            "title": "报告摘要",
            "content": report_context.get("summary", "") if report_context else "无可用报告上下文",
            "evidence_refs": [],
        })

    state["retrieved_context"] = retrieved
    state["evidence_refs"] = list(set(evidence_refs))
    return state


def _extract_evidence_refs(item: dict) -> list[str]:
    refs = item.get("evidence_refs", []) or item.get("evidence", [])
    if isinstance(refs, list):
        return [str(r) for r in refs if r]
    return []


def _item_content(item: dict) -> str:
    fields = ["content", "description", "reason", "detail", "analysis", "name"]
    for f in fields:
        v = item.get(f, "")
        if v:
            return str(v) if isinstance(v, str) else str(v)
    return str(item)
