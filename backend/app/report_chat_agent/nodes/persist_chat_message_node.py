from app.db.session import get_session_local
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.state import ReportChatState


def persist_chat_message_node(state: ReportChatState) -> ReportChatState:
    session_id = state.get("session_id", "")
    runtime_session_id = state.get("runtime_session_id", "")
    trace_id = state.get("trace_id", "")
    report_id = state.get("report_id", "")
    user_id = state.get("user_id", "anonymous")
    user_question = state.get("user_question", "")
    final_answer = state.get("final_answer", "")
    question_scope = state.get("question_scope", "")
    evidence_refs = state.get("evidence_refs", [])
    rag_source_refs = state.get("rag_source_refs", [])
    rag_sources = state.get("rag_sources", []) or state.get("rag_results", [])
    used_rag = state.get("used_rag", False)
    answer_type = state.get("answer_type", "normal")
    query_scope = state.get("query_scope", {})
    errors: list[dict] = state.get("errors", [])

    try:
        rid = int(report_id)
    except (TypeError, ValueError):
        errors.append({"node": "persist_chat_message", "message": f"无效的 report_id: {report_id}"})
        state["errors"] = errors
        return state

    db = get_session_local()()
    try:
        if session_id:
            session = report_chat_repo.ensure_session(
                db,
                session_id=session_id,
                report_id=rid,
                user_id=user_id,
                title="本质安全报告追问",
                scene=state.get("scene", "essential_safety"),
            )
        else:
            session = report_chat_repo.create_session(
                db,
                report_id=rid,
                user_id=user_id,
                title="本质安全报告追问",
                scene=state.get("scene", "essential_safety"),
            )
            state["session_id"] = session.id

        # 正常 API 链路会在 Graph 执行前保存用户问题；保留该分支以兼容
        # 直接调用 Graph 的测试和脚本，避免产生无统一 Session 的消息。
        if not runtime_session_id and user_question:
            runtime_session = report_chat_repo.begin_turn(
                db,
                session=session,
                question=user_question,
                trace_id=trace_id,
            )
            runtime_session_id = runtime_session.id
            state["runtime_session_id"] = runtime_session_id

        if final_answer and runtime_session_id:
            assistant_message = report_chat_repo.complete_turn(
                db,
                session_id=session.id,
                runtime_session_id=runtime_session_id,
                report_id=rid,
                content=final_answer,
                trace_id=trace_id,
                question_scope=question_scope,
                answer_type=answer_type,
                evidence_refs=evidence_refs,
                query_scope=query_scope,
                used_rag=used_rag,
                rag_source_refs=rag_source_refs,
                rag_sources=rag_sources,
            )
            state["message_id"] = assistant_message.id
    finally:
        db.close()

    return state
