from sqlalchemy import select
from sqlalchemy.orm import Session

from app.runtime.models.feedback_model import AiFeedback
from app.runtime.schemas.feedback_schema import FeedbackCreate
from app.utils.ids import new_feedback_id


class FeedbackRepository:
    def create(self, db: Session, payload: FeedbackCreate) -> AiFeedback:
        record = AiFeedback(
            id=new_feedback_id(),
            conversation_id=payload.conversation_id,
            session_id=payload.session_id,
            user_id=payload.user_id,
            rating=payload.rating,
            feedback_type=payload.feedback_type,
            content=payload.content,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_by_id(self, db: Session, feedback_id: str) -> AiFeedback | None:
        return db.get(AiFeedback, feedback_id)

    def update(self, db: Session, feedback_id: str, payload: dict) -> AiFeedback | None:
        record = self.get_by_id(db, feedback_id)
        if record is None:
            return None
        for field, value in payload.items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record

    def update_status(self, db: Session, feedback_id: str, status: str) -> AiFeedback | None:
        return self.get_by_id(db, feedback_id)

    def list_by_session_id(self, db: Session, session_id: str) -> list[AiFeedback]:
        stmt = select(AiFeedback).where(AiFeedback.session_id == session_id).order_by(AiFeedback.created_at.desc())
        return list(db.scalars(stmt).all())
