"""SessionRepository — 运行记录数据访问层"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.runtime.models.session_model import AiSession
from app.runtime.schemas.session_schema import SessionCreate, SessionUpdate
from app.utils.ids import new_session_id
from app.utils.timezone import now_local


class SessionRepository:
    def create(self, db: Session, payload: SessionCreate) -> AiSession:
        record = AiSession(
            id=new_session_id(),
            conversation_id=payload.conversation_id,
            user_id=payload.user_id,
            task_type=payload.task_type,
            input_text=payload.input_text,
            context=payload.context,
            status=payload.status,
            started_at=now_local(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_by_id(self, db: Session, session_id: str) -> AiSession | None:
        return db.get(AiSession, session_id)

    def list_recent(
        self,
        db: Session,
        *,
        session_id: str | None = None,
        status: str | None = None,
        task_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AiSession]:
        stmt = select(AiSession)
        if session_id:
            stmt = stmt.where(AiSession.id == session_id)
        if status:
            statuses = tuple(value.strip() for value in status.split(",") if value.strip())
            if len(statuses) == 1:
                stmt = stmt.where(AiSession.status == statuses[0])
            elif statuses:
                stmt = stmt.where(AiSession.status.in_(statuses))
        if task_type:
            stmt = stmt.where(AiSession.task_type == task_type)
        if date_from:
            stmt = stmt.where(AiSession.created_at >= datetime.combine(date_from, time.min))
        if date_to:
            stmt = stmt.where(AiSession.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
        stmt = stmt.order_by(AiSession.created_at.desc()).offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    def list_by_conversation(self, db: Session, conversation_id: str) -> list[AiSession]:
        stmt = (
            select(AiSession)
            .where(AiSession.conversation_id == conversation_id)
            .order_by(AiSession.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    def list_recent_success_by_conversation(
        self,
        db: Session,
        conversation_id: str,
        limit: int = 6,
    ) -> list[AiSession]:
        """查询最近 N 条成功的对话记录，按时间正序返回"""
        stmt = (
            select(AiSession)
            .where(
                AiSession.conversation_id == conversation_id,
                AiSession.status == "success",
                AiSession.output_text.is_not(None),
            )
            .order_by(AiSession.created_at.desc())
            .limit(limit)
        )
        records = list(db.scalars(stmt).all())
        return list(reversed(records))  # 正序返回给 LLM 上下文

    def update(self, db: Session, session_id: str, payload: SessionUpdate) -> AiSession | None:
        record = self.get_by_id(db, session_id)
        if record is None:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)
        if payload.status in ("success", "failed", "cancelled", "expired"):
            record.finished_at = now_local()
        db.commit()
        db.refresh(record)
        return record

    def update_status(self, db: Session, session_id: str, status: str) -> AiSession | None:
        record = self.get_by_id(db, session_id)
        if record is None:
            return None
        record.status = status
        if status in ("success", "failed", "cancelled", "expired"):
            record.finished_at = now_local()
        db.commit()
        db.refresh(record)
        return record
