"""
AI 对话接口 — POST /ai/chat（同步）和 POST /ai/chat/stream（流式）

同步流程调用 RuntimeService.chat()：
   1. 创建/获取 Conversation
   2. 创建 Session（running）
   3. 加载 Active Prompt
   4. 查询历史消息
   5. 调用 LLM（DeepSeek）
   6. 更新 Session 状态（success/failed）
   7. 返回对话结果

流式流程调用 RuntimeService.chat_stream()，以 SSE 逐 token 输出 LLM 回复。
"""

from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.db.session import get_db
from app.core.schema.response_schema import ApiResponse
from app.runtime.runtime_service import runtime_service


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    user_id: str = "anonymous"
    biz_type: str | None = None
    prompt_code: str | None = None


router = APIRouter()


@router.post("/ai/chat", response_model=ApiResponse[dict])
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    result = runtime_service.chat(
        db=db,
        user_id=payload.user_id,
        message=payload.message,
        conversation_id=payload.conversation_id,
        biz_type=payload.biz_type,
        prompt_code=payload.prompt_code,
    )
    return ApiResponse(data=result)


@router.post("/ai/chat/stream")
async def chat_stream(
    payload: ChatRequest,
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
