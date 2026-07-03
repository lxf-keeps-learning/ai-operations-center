from fastapi import APIRouter

from app.application.agent_service import agent_service
from app.schemas.common import ApiResponse
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter()


@router.post("", response_model=ApiResponse[FeedbackResponse], summary="提交用户反馈")
async def submit_feedback(payload: FeedbackRequest) -> ApiResponse[FeedbackResponse]:
    feedback = agent_service.create_feedback(payload)
    return ApiResponse(data=feedback)
