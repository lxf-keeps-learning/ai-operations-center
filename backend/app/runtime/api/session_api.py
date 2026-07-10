"""
Session 管理接口 — 运行记录 CRUD

Session 代表一次 AI 对话或分析任务的执行记录。
提供创建、查询、更新状态、更新输出等操作。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.runtime.schemas.session_schema import SessionCreate, SessionOutputUpdate, SessionResponse, SessionStatusUpdate, SessionUpdate
from app.runtime.services.session_service import session_service
from app.core.schema.response_schema import ApiResponse
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import NOT_FOUND

router = APIRouter()


@router.post("/runtime/sessions", response_model=ApiResponse[SessionResponse], status_code=201)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)) -> ApiResponse[SessionResponse]:
    result = session_service.create(db, payload)
    return ApiResponse(data=result)


@router.get("/runtime/sessions/{session_id}", response_model=ApiResponse[SessionResponse])
def get_session(session_id: str, db: Session = Depends(get_db)) -> ApiResponse[SessionResponse]:
    result = session_service.get_by_id(db, session_id)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)


@router.patch("/runtime/sessions/{session_id}/status", response_model=ApiResponse[SessionResponse])
def update_session_status(session_id: str, payload: SessionStatusUpdate, db: Session = Depends(get_db)) -> ApiResponse[SessionResponse]:
    update = SessionUpdate(status=payload.status)
    result = session_service.update(db, session_id, update)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)


@router.patch("/runtime/sessions/{session_id}/output", response_model=ApiResponse[SessionResponse])
def update_session_output(session_id: str, payload: SessionOutputUpdate, db: Session = Depends(get_db)) -> ApiResponse[SessionResponse]:
    update = SessionUpdate(output_text=payload.output_text)
    result = session_service.update(db, session_id, update)
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)
