"""
Conversation 管理接口 — 会话 CRUD

Conversation 代表一次完整的对话过程，包含多个 Session（多次问答）。
提供创建、查询、更新状态等操作。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.runtime.schemas.conversation_schema import ConversationCreate, ConversationResponse, ConversationStatusUpdate, ConversationUpdate
from app.runtime.services.conversation_service import conversation_service
from app.runtime.services.session_service import session_service
from app.core.schema.response_schema import ApiResponse
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import NOT_FOUND

router = APIRouter()


@router.get("/runtime/conversations", response_model=ApiResponse[list[dict]])
def list_runtime_conversations(
    user_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    conversations = conversation_service.list_recent(
        db,
        user_id=user_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return ApiResponse(data=[
        {
            "id": item.id,
            "user_id": item.user_id,
            "title": item.title,
            "biz_type": item.biz_type,
            "source": item.source,
            "status": item.status,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in conversations
    ])


@router.post("/runtime/conversations", response_model=ApiResponse[ConversationResponse], status_code=201)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)) -> ApiResponse[ConversationResponse]:
    result = conversation_service.create(db, payload)
    return ApiResponse(data=result)


@router.get("/runtime/conversations/{conversation_id}", response_model=ApiResponse[dict])
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    result = conversation_service.get_by_id(db, conversation_id)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    sessions = session_service.list_by_conversation(db, conversation_id)
    return ApiResponse(data={
        **result.model_dump(),
        "sessions": [session.model_dump() for session in sessions],
    })


@router.patch("/runtime/conversations/{conversation_id}/status", response_model=ApiResponse[ConversationResponse])
def update_conversation_status(conversation_id: str, payload: ConversationStatusUpdate, db: Session = Depends(get_db)) -> ApiResponse[ConversationResponse]:
    update = ConversationUpdate(status=payload.status)
    result = conversation_service.update(db, conversation_id, update)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)
