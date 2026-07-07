from sqlalchemy import select
from sqlalchemy.orm import Session

from app.runtime.models.conversation_model import AiConversation
from app.runtime.schemas.conversation_schema import ConversationCreate, ConversationUpdate
from app.utils.ids import new_conversation_id


class ConversationRepository:
    def create(self, db: Session, payload: ConversationCreate) -> AiConversation:
        record = AiConversation(
            id=new_conversation_id(),
            user_id=payload.user_id,
            title=payload.title,
            biz_type=payload.biz_type,
            source=payload.source,
            status=payload.status,
            meta=payload.meta,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def get_by_id(self, db: Session, conversation_id: str) -> AiConversation | None:
        return db.get(AiConversation, conversation_id)

    def update(self, db: Session, conversation_id: str, payload: ConversationUpdate) -> AiConversation | None:
        record = self.get_by_id(db, conversation_id)
        if record is None:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(record, field, value)
        db.commit()
        db.refresh(record)
        return record

    def update_status(self, db: Session, conversation_id: str, status: str) -> AiConversation | None:
        record = self.get_by_id(db, conversation_id)
        if record is None:
            return None
        record.status = status
        db.commit()
        db.refresh(record)
        return record
