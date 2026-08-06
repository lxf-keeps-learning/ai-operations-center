from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.exception.error_code import INVALID_STATUS_TRANSITION
from app.core.schema.response_schema import ApiResponse
from app.db.session import get_db
from app.operation_inbox.repository import operation_inbox_repo
from app.operation_inbox.schemas import OperatorActionRequest, ResolveMessageRequest

router = APIRouter(tags=["operation-inbox"])


def _serialize(message, session) -> dict:
    context = session.context if session is not None and isinstance(session.context, dict) else {}
    return {
        "id": message.id,
        "runtime_session_id": message.runtime_session_id,
        "report_chat_message_id": message.report_chat_message_id,
        "report_id": message.report_id,
        "priority": message.priority,
        "status": message.status,
        "assignee_id": message.assignee_id,
        "claimed_at": message.claimed_at.isoformat() if message.claimed_at else None,
        "lease_expires_at": message.lease_expires_at.isoformat() if message.lease_expires_at else None,
        "resolved_at": message.resolved_at.isoformat() if message.resolved_at else None,
        "resolution_note": message.resolution_note,
        "retry_count": message.retry_count,
        "error_message": message.error_message or (session.error_message if session else None),
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None,
        "ai_status": session.status if session else None,
        "task_type": session.task_type if session else "operation_analysis",
        "user_id": session.user_id if session else None,
        "conversation_id": session.conversation_id if session else None,
        "input_text": session.input_text if session else None,
        "output_text": session.output_text if session else None,
        "trace_id": context.get("trace_id") or (message.runtime_session_id if session is None else None),
    }


def _conflict(message: str) -> ApiResponse[None]:
    return ApiResponse(code=INVALID_STATUS_TRANSITION.code, message=message)


@router.get("/operation/messages")
def list_messages(
    status: str | None = Query(default=None),
    assignee_id: str | None = Query(default=None),
    priority: int | None = Query(default=None),
    report_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    rows = operation_inbox_repo.list_with_sessions(
        db,
        status=status,
        assignee_id=assignee_id,
        priority=priority,
        report_id=report_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return ApiResponse(data=[_serialize(message, session) for message, session in rows])


@router.get("/operation/messages/summary")
def message_summary(
    assignee_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, int]]:
    return ApiResponse(data=operation_inbox_repo.summary(db, assignee_id=assignee_id))


@router.get("/operation/messages/{message_id}")
def message_detail(message_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    row = operation_inbox_repo.get_with_session(db, message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="运营消息不存在")
    return ApiResponse(data=_serialize(*row))


@router.post("/operation/messages/{message_id}/claim")
def claim_message(
    message_id: str,
    payload: OperatorActionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict] | ApiResponse[None]:
    if operation_inbox_repo.claim(db, message_id, payload.operator_id) is None:
        return _conflict("消息已被其他运营人员领取或当前不可领取")
    return ApiResponse(data=_serialize(*operation_inbox_repo.get_with_session(db, message_id)))


@router.post("/operation/messages/{message_id}/release")
def release_message(
    message_id: str,
    payload: OperatorActionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict] | ApiResponse[None]:
    if operation_inbox_repo.release(db, message_id, payload.operator_id) is None:
        return _conflict("只能释放自己领取中的消息")
    return ApiResponse(data=_serialize(*operation_inbox_repo.get_with_session(db, message_id)))


@router.post("/operation/messages/{message_id}/resolve")
def resolve_message(
    message_id: str,
    payload: ResolveMessageRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict] | ApiResponse[None]:
    if operation_inbox_repo.resolve(db, message_id, payload.operator_id, payload.note) is None:
        return _conflict("只能完成自己领取中的消息")
    return ApiResponse(data=_serialize(*operation_inbox_repo.get_with_session(db, message_id)))


@router.post("/operation/messages/{message_id}/reopen")
def reopen_message(
    message_id: str,
    payload: OperatorActionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict] | ApiResponse[None]:
    if operation_inbox_repo.reopen(db, message_id, payload.operator_id) is None:
        return _conflict("只有已完成的消息可以重新打开")
    return ApiResponse(data=_serialize(*operation_inbox_repo.get_with_session(db, message_id)))


@router.post("/operation/messages/{message_id}/retry")
def retry_message(
    message_id: str,
    payload: OperatorActionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict] | ApiResponse[None]:
    if operation_inbox_repo.retry(db, message_id, payload.operator_id) is None:
        return _conflict("只有失败的消息可以重试")
    return ApiResponse(data=_serialize(*operation_inbox_repo.get_with_session(db, message_id)))
