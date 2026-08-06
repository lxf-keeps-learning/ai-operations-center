"""
Session 管理接口 — 运行记录 CRUD

Session 代表一次 AI 对话或分析任务的执行记录。
提供创建、查询、更新状态、更新输出等操作。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.runtime.schemas.session_schema import SessionCreate, SessionOutputUpdate, SessionResponse, SessionStatusUpdate, SessionUpdate
from app.runtime.schemas.status import SESS_CANCEL_REQUESTED, SESS_RUNNING
from app.runtime.execution_control import runtime_execution_registry
from app.runtime.services.session_service import session_service
from app.core.schema.response_schema import ApiResponse
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import NOT_FOUND, PARAM_ERROR

router = APIRouter()


@router.get("/runtime/sessions", response_model=ApiResponse[list[SessionResponse]])
def list_sessions(
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[list[SessionResponse]]:
    result = session_service.list_recent(
        db,
        status=status,
        task_type=task_type,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return ApiResponse(data=result)


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


@router.post("/runtime/sessions/{session_id}/cancel", response_model=ApiResponse[SessionResponse])
def cancel_session(session_id: str, db: Session = Depends(get_db)) -> ApiResponse[SessionResponse]:
    current = session_service.get_by_id(db, session_id)
    if current is None:
        raise AppException.from_error_code(NOT_FOUND)
    if current.status != SESS_RUNNING:
        raise AppException.from_error_code(
            PARAM_ERROR,
            message=f"Session 当前状态为 {current.status}，不可取消",
        )
    if not runtime_execution_registry.request_cancel(session_id):
        raise AppException.from_error_code(
            PARAM_ERROR,
            message="Session 当前不在可控制的运行上下文中",
        )
    result = session_service.update(
        db,
        session_id,
        SessionUpdate(status=SESS_CANCEL_REQUESTED),
    )
    if result is None:
        raise AppException.from_error_code(NOT_FOUND)
    return ApiResponse(data=result)
