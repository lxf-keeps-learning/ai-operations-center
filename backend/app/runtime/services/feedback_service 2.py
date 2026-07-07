from sqlalchemy.orm import Session

from app.runtime.repositories.feedback_repository import FeedbackRepository
from app.runtime.schemas.feedback_schema import FeedbackCreate, FeedbackResponse

_repo = FeedbackRepository()


class FeedbackService:
    def create(self, db: Session, payload: FeedbackCreate) -> FeedbackResponse:
        record = _repo.create(db, payload)
        return FeedbackResponse.model_validate(record)


feedback_service = FeedbackService()
