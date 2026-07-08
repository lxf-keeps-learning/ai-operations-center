from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.schema.response_schema import ApiResponse
from app.db.session import get_db
from app.report_chat_agent.repositories import report_chat_repo
from app.report_chat_agent.schemas.request import CreateSessionRequest, SendMessageRequest
from app.report_chat_agent.schemas.response import (
    ChatMessageResponse,
    CreateSessionResponse,
    GetMessagesResponse,
    SendMessageResponse,
)
from app.report_chat_agent.service import create_chat_session, send_chat_message

router = APIRouter()


@router.post("/reports/{report_id}/chat/sessions", response_model=ApiResponse[CreateSessionResponse])
def create_session(report_id: int, payload: CreateSessionRequest) -> ApiResponse[CreateSessionResponse]:
    session = create_chat_session(
        report_id=report_id,
        user_id=payload.user_id,
    )
    data = CreateSessionResponse(
        session_id=session["session_id"],
        report_id=session["report_id"],
        title=session["title"],
    )
    return ApiResponse(data=data)


@router.get("/chat/sessions/{session_id}/messages", response_model=ApiResponse[GetMessagesResponse])
def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse[GetMessagesResponse]:
    session = report_chat_repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = report_chat_repo.list_messages(db, session_id)
    msg_responses = [
        ChatMessageResponse(
            role=m.role,
            content=m.content,
            evidence_refs=m.evidence_refs or [],
            question_scope=m.question_scope,
            created_at=m.created_at.isoformat() if m.created_at else "",
            used_rag=_message_used_rag(m),
            rag_source_refs=_message_rag_source_refs(m),
            rag_sources=_message_rag_sources(m),
        )
        for m in messages
    ]
    data = GetMessagesResponse(session_id=session_id, messages=msg_responses)
    return ApiResponse(data=data)


@router.post("/chat/sessions/{session_id}/messages", response_model=ApiResponse[SendMessageResponse])
def send_message(
    session_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[SendMessageResponse]:
    session = report_chat_repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.report_id != payload.report_id:
        raise HTTPException(status_code=400, detail="会话与报告不匹配")

    result = send_chat_message(
        session_id=session_id,
        report_id=payload.report_id,
        question=payload.question,
        user_id=session.user_id,
    )

    data = SendMessageResponse(
        trace_id=result.get("trace_id", ""),
        session_id=session_id,
        message_id=result.get("message_id", ""),
        question_scope=result.get("question_scope", "report_internal"),
        answer=result.get("final_answer", ""),
        evidence_refs=result.get("evidence_refs", []),
        query_scope=result.get("query_scope", {}),
        answer_type=result.get("answer_type", "normal"),
        used_rag=result.get("used_rag", False),
        rag_source_refs=result.get("rag_source_refs", []),
        rag_sources=result.get("rag_sources", []) or result.get("rag_results", []),
    )
    return ApiResponse(data=data)


def _message_used_rag(message: object) -> bool:
    """读取历史消息的 RAG 标记，优先兼容已有 JSON 存储。"""
    direct = getattr(message, "used_rag", None)
    if direct is not None:
        return bool(direct)
    query_scope = getattr(message, "query_scope", None) or {}
    return bool(query_scope.get("used_rag", False)) if isinstance(query_scope, dict) else False


def _message_rag_source_refs(message: object) -> list[str]:
    """读取历史消息的 RAG 来源引用，旧表场景下来源于 query_scope。"""
    direct = getattr(message, "rag_source_refs", None)
    if direct:
        return [str(ref) for ref in direct if ref]
    query_scope = getattr(message, "query_scope", None) or {}
    if not isinstance(query_scope, dict):
        return []
    refs = query_scope.get("rag_source_refs", [])
    return [str(ref) for ref in refs if ref] if isinstance(refs, list) else []


def _message_rag_sources(message: object) -> list[dict]:
    """读取历史消息中的 RAG 依据明细，供前端展示文档标题和来源。"""
    query_scope = getattr(message, "query_scope", None) or {}
    if not isinstance(query_scope, dict):
        return []
    sources = query_scope.get("rag_sources", [])
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)]
