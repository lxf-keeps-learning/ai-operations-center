from fastapi import APIRouter

from app.core.context.context_holder import get_page_context, get_request_context, get_user_context
from app.core.schema.response_schema import ApiResponse

router = APIRouter()


@router.get("/context/current", summary="当前请求上下文")
async def get_current_context() -> ApiResponse[dict]:
    return ApiResponse(
        data={
            "requestContext": get_request_context().to_dict(),
            "userContext": get_user_context().to_dict(),
            "pageContext": get_page_context().to_dict(),
        }
    )
