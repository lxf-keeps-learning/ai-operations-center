from sqlalchemy.orm import Session

from app.operation_agent.models.analysis_record_model import OperationAnalysisRecord
from app.operation_agent.repositories.analysis_record_repo import analysis_record_repo
from app.report_chat_agent.state import ReportChatState


def load_report_context_node(state: ReportChatState, db: Session) -> ReportChatState:
    report_id = state.get("report_id", "")
    errors: list[dict] = state.get("errors", [])

    # Graph 单测、离线调试或上游服务可能已经把报告上下文放入 State。
    # 这种情况下直接复用，避免再次访问数据库；线上 API 的初始 State 为空，仍会正常加载 DB。
    if _has_preloaded_report_context(state):
        state["errors"] = errors
        return state

    if not report_id:
        errors.append({"node": "load_report_context", "message": "report_id 为空"})
        state["errors"] = errors
        return state

    try:
        rid = int(report_id)
    except (ValueError, TypeError):
        errors.append({"node": "load_report_context", "message": f"无效的 report_id: {report_id}"})
        state["errors"] = errors
        return state

    record: OperationAnalysisRecord | None = analysis_record_repo.get_by_id(db, rid)
    if record is None:
        errors.append({"node": "load_report_context", "message": f"报告不存在: report_id={report_id}"})
        state["errors"] = errors
        return state

    scene_map = {
        "safety": "essential_safety",
        "maintenance": "equipment_maintenance",
        "business": "business_improvement",
        "capability": "capability_enhancement",
    }
    domain = record.domain or "safety"
    state["scene"] = scene_map.get(domain, "essential_safety")

    abnormal_raw = record.abnormal_items_json or {}
    risk_raw = record.risk_items_json or {}
    advice_raw = record.advice_items_json or {}
    evidence_raw = record.evidence_json or {}

    state["report_context"] = {
        "title": record.report_name or "运营分析报告",
        "summary": record.summary_text or "",
        "risk_level": _extract_risk_level(risk_raw),
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "domain": domain,
    }

    state["report_sections"] = _split_sections(record.final_answer_markdown or "")
    state["abnormal_items"] = _extract_list(abnormal_raw, "items")
    state["risk_items"] = _extract_list(risk_raw, "items")
    state["advice_items"] = _extract_list(advice_raw, "items")
    state["evidence"] = _extract_list(evidence_raw, "items") or _extract_list(evidence_raw, "evidence")

    state["errors"] = errors
    return state


def _has_preloaded_report_context(state: ReportChatState) -> bool:
    report_context = state.get("report_context", {})
    if not isinstance(report_context, dict):
        return False
    if report_context.get("summary") or report_context.get("title"):
        return True
    context_fields = (
        "report_sections",
        "abnormal_items",
        "risk_items",
        "advice_items",
        "evidence",
    )
    return any(bool(state.get(field, [])) for field in context_fields)


def _extract_risk_level(risk_raw: dict) -> str:
    items = risk_raw.get("items", []) if isinstance(risk_raw, dict) else []
    if not items:
        return "unknown"
    severities = [str(item.get("severity", "")) for item in items if item.get("severity")]
    if "critical" in severities:
        return "critical"
    if "high" in severities:
        return "high"
    if "warning" in severities:
        return "warning"
    return "low"


def _extract_list(raw: dict | list, key: str) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        items = raw.get(key, [])
        return items if isinstance(items, list) else []
    return []


def _split_sections(markdown: str) -> list[dict]:
    sections: list[dict] = []
    lines = markdown.split("\n")
    current: dict | None = None

    for line in lines:
        if line.startswith("### "):
            if current:
                sections.append(current)
            current = {"title": line[4:].strip(), "content": "", "lines": []}
        elif line.startswith("## "):
            if current:
                sections.append(current)
            current = {"title": line[3:].strip(), "content": "", "lines": []}
        else:
            if current:
                current["lines"].append(line)
                current["content"] = "\n".join(current["lines"])

    if current:
        sections.append(current)

    return sections
