from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.runtime.schemas.trace_schema import TraceCreate, TraceResponse
from app.runtime.services.trace_service import trace_service
from app.core.schema.response_schema import ApiResponse

router = APIRouter()


@router.post("/runtime/traces", response_model=ApiResponse[TraceResponse], status_code=201)
def create_trace(payload: TraceCreate, db: Session = Depends(get_db)) -> ApiResponse[TraceResponse]:
    result = trace_service.create(db, payload)
    return ApiResponse(data=result)


@router.get("/runtime/traces/{trace_id}", response_model=ApiResponse[list[TraceResponse]])
def get_trace(trace_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[TraceResponse]]:
    results = trace_service.list_by_trace_id(db, trace_id)
    return ApiResponse(data=results)


@router.get(
    "/runtime/sessions/{session_id}/traces",
    response_model=ApiResponse[list[TraceResponse]],
)
def get_session_traces(
    session_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse[list[TraceResponse]]:
    results = trace_service.list_by_session_id(db, session_id)
    return ApiResponse(data=results)
