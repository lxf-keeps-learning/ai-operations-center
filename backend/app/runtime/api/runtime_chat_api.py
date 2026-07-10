"""
Runtime 聊天接口 — POST /runtime/chat（同步）和 POST /runtime/chat/stream（流式）

与 /ai/chat 功能相同，多一个路由入口。
流式版本以 SSE 逐 token 输出 LLM 回复。
"""

from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.db.session import get_db
from app.core.schema.response_schema import ApiResponse
from app.runtime.runtime_service import runtime_service


class RuntimeChatRequest(BaseModel):
    conversation_id: str | None = None
    user_id: str = "anonymous"
    biz_type: str | None = None
    prompt_code: str | None = None
    message: str = Field(min_length=1)


router = APIRouter()


@router.post("/runtime/chat", response_model=ApiResponse[dict])
def runtime_chat(payload: RuntimeChatRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    result = runtime_service.chat(
        db=db,
        user_id=payload.user_id,
        message=payload.message,
        conversation_id=payload.conversation_id,
        biz_type=payload.biz_type,
        prompt_code=payload.prompt_code,
    )
    return ApiResponse(data=result)


@router.post("/runtime/chat/stream")
async def runtime_chat_stream(
    payload: RuntimeChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in runtime_service.chat_stream(
            db=db,
            user_id=payload.user_id,
            message=payload.message,
            conversation_id=payload.conversation_id,
            biz_type=payload.biz_type,
            prompt_code=payload.prompt_code,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
