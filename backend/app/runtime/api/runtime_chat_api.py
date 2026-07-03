from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
