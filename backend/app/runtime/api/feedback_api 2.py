from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.runtime.schemas.feedback_schema import FeedbackCreate, FeedbackResponse
from app.runtime.services.feedback_service import feedback_service
from app.core.schema.response_schema import ApiResponse
from app.runtime.repositories.feedback_repository import FeedbackRepository

router = APIRouter()
_repo = FeedbackRepository()


@router.post("/runtime/feedback", response_model=ApiResponse[dict], status_code=201)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)) -> ApiResponse[dict]:
    result = feedback_service.create(db, payload)
    return ApiResponse(data={"feedback_id": result.id})


@router.get("/runtime/sessions/{session_id}/feedback", response_model=ApiResponse[list[FeedbackResponse]])
def get_session_feedback(session_id: str, db: Session = Depends(get_db)) -> ApiResponse[list[FeedbackResponse]]:
    records = _repo.list_by_session_id(db, session_id)
    results = [FeedbackResponse.model_validate(r) for r in records]
    return ApiResponse(data=results)
