"""
上下文查询接口 — GET /context/current

返回当前 HTTP 请求的三层上下文：
  - requestContext: 请求元信息（traceId、IP、User-Agent、method、path）
  - userContext: 用户身份信息（userId、username、orgId、roles）
  - pageContext: 页面上下文（pageCode、filters、selectedObjectId）

用于前端 Infra Console 的 Context 示例页面，
展示 Trace 中间件注入的上下文数据结构。
"""

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
