from sqlalchemy.orm import Session

from app.runtime.repositories.session_repository import SessionRepository
from app.runtime.schemas.session_schema import SessionCreate, SessionResponse, SessionUpdate
from app.runtime.schemas.status import SESS_CANCELLED, SESS_SUCCESS

_repo = SessionRepository()


class SessionService:
    def create(self, db: Session, payload: SessionCreate) -> SessionResponse:
        record = _repo.create(db, payload)
        return SessionResponse.model_validate(record)

    def get_by_id(self, db: Session, session_id: str) -> SessionResponse | None:
        record = _repo.get_by_id(db, session_id)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def list_recent_messages(
        self,
        db: Session,
        conversation_id: str,
        limit: int = 6,
    ) -> list[dict[str, str]]:
        records = _repo.list_recent_success_by_conversation(db, conversation_id, limit)
        messages: list[dict[str, str]] = []
        for record in records:
            messages.append({"role": "user", "content": record.input_text})
            if record.output_text:
                messages.append({"role": "assistant", "content": record.output_text})
        return messages

    def update(
        self,
        db: Session,
        session_id: str,
        payload: SessionUpdate,
    ) -> SessionResponse | None:
        record = _repo.update(db, session_id, payload)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def mark_success(self, db: Session, session_id: str) -> SessionResponse | None:
        record = _repo.update_status(db, session_id, SESS_SUCCESS)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def mark_cancelled(self, db: Session, session_id: str) -> SessionResponse | None:
        record = _repo.update_status(db, session_id, SESS_CANCELLED)
        if record is None:
            return None
        return SessionResponse.model_validate(record)

    def update_output(
        self,
        db: Session,
        session_id: str,
        output_text: str,
        status: str = SESS_SUCCESS,
    ) -> SessionResponse | None:
        return self.update(db, session_id, SessionUpdate(output_text=output_text, status=status))


session_service = SessionService()
