from sqlalchemy.orm import Session

from app.runtime.repositories.conversation_repository import ConversationRepository
from app.runtime.schemas.conversation_schema import ConversationCreate, ConversationResponse, ConversationUpdate
from app.runtime.schemas.status import CONV_ACTIVE, CONV_CLOSED

_repo = ConversationRepository()


class ConversationService:
    def create(self, db: Session, payload: ConversationCreate) -> ConversationResponse:
        record = _repo.create(db, payload)
        return ConversationResponse.model_validate(record)

    def get_by_id(self, db: Session, conversation_id: str) -> ConversationResponse | None:
        record = _repo.get_by_id(db, conversation_id)
        if record is None:
            return None
        return ConversationResponse.model_validate(record)

    def update(self, db: Session, conversation_id: str, payload: ConversationUpdate) -> ConversationResponse | None:
        record = _repo.update(db, conversation_id, payload)
        if record is None:
            return None
        return ConversationResponse.model_validate(record)

    def close(self, db: Session, conversation_id: str) -> ConversationResponse | None:
        record = _repo.update_status(db, conversation_id, CONV_CLOSED)
        if record is None:
            return None
        return ConversationResponse.model_validate(record)


conversation_service = ConversationService()
