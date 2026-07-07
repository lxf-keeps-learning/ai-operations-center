from sqlalchemy.orm import Session

from app.runtime.repositories.trace_repository import TraceRepository
from app.runtime.schemas.trace_schema import TraceCreate, TraceResponse

_repo = TraceRepository()


class TraceService:
    def create(self, db: Session, payload: TraceCreate) -> TraceResponse:
        record = _repo.create(db, payload)
        return TraceResponse.model_validate(record)

    def list_by_trace_id(self, db: Session, trace_id: str) -> list[TraceResponse]:
        records = _repo.list_by_trace_id(db, trace_id)
        return [TraceResponse.model_validate(r) for r in records]

    def list_by_session_id(self, db: Session, session_id: str) -> list[TraceResponse]:
        records = _repo.list_by_session_id(db, session_id)
        return [TraceResponse.model_validate(r) for r in records]


trace_service = TraceService()
