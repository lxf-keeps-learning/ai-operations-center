from datetime import datetime
from typing import TypedDict

from sqlalchemy.orm import Session

from app.operation_inbox.models import OperationMessage
from app.operation_inbox.repository import OperationMessageRepository
from app.operation_inbox.status import OP_AWAITING_REVIEW


class OperationMessageData(TypedDict):
    id: str
    runtime_session_id: str
    report_chat_message_id: str | None
    report_id: int | None
    priority: int
    status: str
    assignee_id: str | None
    claimed_at: datetime | None
    lease_expires_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None
    retry_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class OperationMessageService:
    def __init__(self, repository: OperationMessageRepository | None = None) -> None:
        self.repository = repository or OperationMessageRepository()

    def enqueue(
        self,
        db: Session,
        *,
        runtime_session_id: str,
        report_chat_message_id: str | None = None,
        report_id: int | None = None,
        priority: int = 0,
        status: str = OP_AWAITING_REVIEW,
    ) -> OperationMessageData:
        message = self.repository.enqueue(
            db,
            runtime_session_id=runtime_session_id,
            report_chat_message_id=report_chat_message_id,
            report_id=report_id,
            priority=priority,
            status=status,
        )
        return self._serialize(message)

    def list_messages(
        self,
        db: Session,
        *,
        status: str | None = None,
        assignee_id: str | None = None,
        priority: int | None = None,
        report_id: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[OperationMessageData]:
        messages = self.repository.list(
            db,
            status=status,
            assignee_id=assignee_id,
            priority=priority,
            report_id=report_id,
            offset=offset,
            limit=limit,
        )
        return [self._serialize(message) for message in messages]

    def summary(self, db: Session) -> dict[str, int]:
        return self.repository.count_by_status(db)

    @staticmethod
    def _serialize(message: OperationMessage) -> OperationMessageData:
        return {
            "id": message.id,
            "runtime_session_id": message.runtime_session_id,
            "report_chat_message_id": message.report_chat_message_id,
            "report_id": message.report_id,
            "priority": message.priority,
            "status": message.status,
            "assignee_id": message.assignee_id,
            "claimed_at": message.claimed_at,
            "lease_expires_at": message.lease_expires_at,
            "resolved_at": message.resolved_at,
            "resolution_note": message.resolution_note,
            "retry_count": message.retry_count,
            "error_message": message.error_message,
            "created_at": message.created_at,
            "updated_at": message.updated_at,
        }


operation_message_service = OperationMessageService()


def enqueue_for_review(
    db: Session,
    *,
    runtime_session_id: str,
    report_chat_message_id: str | None = None,
    report_id: int | None = None,
    priority: int = 0,
    status: str = OP_AWAITING_REVIEW,
    error_message: str | None = None,
) -> OperationMessage:
    """Create one review record per runtime execution.

    The unique runtime-session constraint makes this safe to call from both a
    normal completion path and any retrying caller.
    """
    message = operation_message_service.repository.enqueue(
        db,
        runtime_session_id=runtime_session_id,
        report_chat_message_id=report_chat_message_id,
        report_id=report_id,
        priority=priority,
        status=status,
    )
    if error_message and not message.error_message:
        message.error_message = error_message[:65535]
        db.commit()
        db.refresh(message)
    return message
