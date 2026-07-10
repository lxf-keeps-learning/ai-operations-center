"""
Conversation 管理接口 — 会话 CRUD

Conversation 代表一次完整的对话过程，包含多个 Session（多次问答）。
提供创建、查询、更新状态等操作。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.runtime.schemas.conversation_schema import ConversationCreate, ConversationResponse, ConversationStatusUpdate, ConversationUpdate
from app.runtime.services.conversation_service import conversation_service
from app.core.schema.response_schema import ApiResponse
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import NOT_FOUND

router = APIRouter()


@router.post("/runtime/conversations", response_model=ApiResponse[ConversationResponse], status_code=201)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)) -> ApiResponse[ConversationResponse]:
    result = conversation_service.create(db, payload)
    return ApiResponse(data=result)


@router.get("/runtime/conversations/{conversation_id}", response_model=ApiResponse[ConversationResponse])
def get_conversation(conversation_id: str, db: Session = Depends(get_db)) -> ApiResponse[ConversationResponse]:
    result = conversation_service.get_by_id(db, conversation_id)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)


@router.patch("/runtime/conversations/{conversation_id}/status", response_model=ApiResponse[ConversationResponse])
def update_conversation_status(conversation_id: str, payload: ConversationStatusUpdate, db: Session = Depends(get_db)) -> ApiResponse[ConversationResponse]:
    update = ConversationUpdate(status=payload.status)
    result = conversation_service.update(db, conversation_id, update)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)
