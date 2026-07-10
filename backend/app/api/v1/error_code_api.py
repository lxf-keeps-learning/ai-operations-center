"""
错误码查询接口 — GET /errors/codes

返回系统中所有已注册的业务错误码列表（code / message / httpStatus / description）。
前端用于错误码说明页面展示和错误提示信息的国际化。
"""

from fastapi import APIRouter

from app.core.exception.error_code import ALL_CODES
from app.core.schema.response_schema import ApiResponse

router = APIRouter()


@router.get("/errors/codes", summary="业务错误码列表")
async def get_error_codes() -> ApiResponse[list[dict]]:
    return ApiResponse(
        data=[
            {
                "code": ec.code,
                "message": ec.message,
                "httpStatus": ec.http_status,
                "description": ec.description,
            }
            for ec in ALL_CODES
        ]
    )
