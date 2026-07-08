from app.report_chat_agent.graph import report_chat_graph
from app.db.session import get_session_local
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.state import ReportChatState
from app.utils.ids import new_trace_id


def create_chat_session(report_id: int, user_id: str = "anonymous") -> dict:
    db = get_session_local()()
    try:
        session = report_chat_repo.get_or_create_session(
            db,
            report_id=report_id,
            user_id=user_id,
            title="本质安全报告追问",
            scene="essential_safety",
        )
        return {
            "session_id": session.id,
            "report_id": session.report_id,
            "title": session.title,
        }
    finally:
        db.close()


def _extract_domain(result: ReportChatState) -> str:
    report_context = result.get("report_context", {})
    domain = report_context.get("domain", "") if report_context else ""
    if domain:
        return domain
    scene = result.get("scene", "")
    scene_to_domain = {
        "essential_safety": "safety",
        "equipment_maintenance": "maintenance",
        "business_improvement": "business",
        "capability_enhancement": "capability",
    }
    return scene_to_domain.get(scene, "safety")


def save_report_chat_usage(result: ReportChatState) -> None:
    llm_usages: list[dict] = result.get("llm_usages", [])
    if not llm_usages:
        return
    from app.operation_agent.models.ai_usage_record_model import OperationAiUsageRecord
    from app.operation_agent.repositories.ai_usage_repo import ai_usage_repo

    domain = _extract_domain(result)
    db = get_session_local()()
    try:
        records = []
        for usage in llm_usages:
            records.append(OperationAiUsageRecord(
                trace_id=result.get("trace_id", ""),
                analysis_record_id=None,
                user_id=result.get("user_id", "anonymous"),
                action_type=usage.get("action_type", "report_answer"),
                domain=domain,
                model_provider="deepseek",
                model_name=usage.get("model_name", "deepseek-chat"),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                success=usage.get("success", 1),
                error_message=usage.get("error_message"),
            ))
        ai_usage_repo.bulk_create(db, records)
    finally:
        db.close()


def send_chat_message(
    session_id: str,
    report_id: int,
    question: str,
    user_id: str = "anonymous",
) -> ReportChatState:
    initial_state: ReportChatState = {
        "trace_id": new_trace_id(),
        "report_id": str(report_id),
        "session_id": session_id,
        "user_id": user_id,
        "user_question": question,
        "scene": "essential_safety",
        "report_context": {},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_rag": False,
        "rag_reason": "",
        "rag_query": {},
        "rag_results": [],
        "rag_source_refs": [],
        "rag_sources": [],
        "used_rag": False,
        "merged_context": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "errors": [],
        "llm_usages": [],
    }

    result = report_chat_graph.invoke(initial_state)
    save_report_chat_usage(result)
    return result
