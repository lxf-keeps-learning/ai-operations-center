from fastapi import APIRouter, HTTPException, Query

from app.application.agent_service import agent_service
from app.schemas.common import ApiResponse, PaginatedResult
from app.schemas.conversation import ConversationDetail, ConversationSummary
from app.utils.ids import new_trace_id

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[PaginatedResult[ConversationSummary]],
    summary="查询会话列表",
)
async def list_conversations(
    agent_code: str | None = Query(default=None, description="Agent 编码"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[PaginatedResult[ConversationSummary]]:
    result = agent_service.list_conversations(agent_code=agent_code, page=page, page_size=page_size)
    return ApiResponse(message="success", traceId=new_trace_id(), data=result)


@router.get(
    "/{conversation_id}",
    response_model=ApiResponse[ConversationDetail],
    summary="查询会话详情",
)
async def get_conversation(conversation_id: str) -> ApiResponse[ConversationDetail]:
    conversation = agent_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    return ApiResponse(message="success", traceId=new_trace_id(), data=conversation)


@router.delete("/{conversation_id}", response_model=ApiResponse[bool], summary="删除会话")
async def delete_conversation(conversation_id: str) -> ApiResponse[bool]:
    deleted = agent_service.delete_conversation(conversation_id)
    return ApiResponse(message="success", traceId=new_trace_id(), data=deleted)
