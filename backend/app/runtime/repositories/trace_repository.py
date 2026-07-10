"""TraceRepository — 全链路追踪数据访问层"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.runtime.models.trace_model import AiTrace
from app.runtime.schemas.trace_schema import TraceCreate
from app.utils.ids import new_span_id


class TraceRepository:
    def create(self, db: Session, payload: TraceCreate) -> AiTrace:
        record = AiTrace(
            id=new_span_id(),
            trace_id=payload.trace_id,
            span_id=payload.span_id,
            parent_span_id=payload.parent_span_id,
            conversation_id=payload.conversation_id,
            session_id=payload.session_id,
            span_type=payload.span_type,
            graph_name=payload.graph_name,
            node_name=payload.node_name,
            tool_name=payload.tool_name,
            model_name=payload.model_name,
            prompt_id=payload.prompt_id,
            prompt_code=payload.prompt_code,
            prompt_version=payload.prompt_version,
            prompt_snapshot=payload.prompt_snapshot,
            input_data=payload.input_data,
            output_data=payload.output_data,
            cost_ms=payload.cost_ms,
            prompt_tokens=payload.prompt_tokens,
            completion_tokens=payload.completion_tokens,
            total_tokens=payload.total_tokens,
            status=payload.status,
            error_code=payload.error_code,
            error_message=payload.error_message,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_by_id(self, db: Session, trace_id: str) -> AiTrace | None:
        return db.get(AiTrace, trace_id)

    def update(self, db: Session, trace_id: str, payload: dict) -> AiTrace | None:
        record = self.get_by_id(db, trace_id)
        if record is None:
            return None
        for field, value in payload.items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record

    def update_status(self, db: Session, trace_id: str, status: str) -> AiTrace | None:
        record = self.get_by_id(db, trace_id)
        if record is None:
            return None
        record.status = status
        db.commit()
        db.refresh(record)
        return record

    def list_by_trace_id(self, db: Session, trace_id: str) -> list[AiTrace]:
        """按 trace_id 查询整条链路的所有 Span，按创建时间升序"""
        stmt = (
            select(AiTrace)
            .where(AiTrace.trace_id == trace_id)
            .order_by(AiTrace.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    def list_by_session_id(self, db: Session, session_id: str) -> list[AiTrace]:
        """按 session_id 查询某次运行的所有 Trace 记录"""
        stmt = (
            select(AiTrace)
            .where(AiTrace.session_id == session_id)
            .order_by(AiTrace.created_at.asc())
        )
        return list(db.scalars(stmt).all())
