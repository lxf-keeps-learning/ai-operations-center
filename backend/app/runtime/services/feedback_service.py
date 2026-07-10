"""FeedbackService — 用户反馈业务逻辑

用户可以对 LLM 的某次回复进行点赞/点踩及文字评价，
用于后续的模型效果评估和 Prompt 优化迭代。
反馈关联到具体的 Session（运行记录），便于追溯上下文。
"""

from sqlalchemy.orm import Session

from app.runtime.repositories.feedback_repository import FeedbackRepository
from app.runtime.schemas.feedback_schema import FeedbackCreate, FeedbackResponse

_repo = FeedbackRepository()


class FeedbackService:
    def create(self, db: Session, payload: FeedbackCreate) -> FeedbackResponse:
        """
        提交用户反馈（点赞/点踩 + 可选文字评价）。
        payload 需包含 session_id、rating（thumbs_up / thumbs_down）和可选的 comment。
        """
        record = _repo.create(db, payload)
        return FeedbackResponse.model_validate(record)

    def list_by_session_id(self, db: Session, session_id: str) -> list[FeedbackResponse]:
        """查询某次运行的所有反馈记录"""
        records = _repo.list_by_session_id(db, session_id)
        return [FeedbackResponse.model_validate(r) for r in records]


feedback_service = FeedbackService()
