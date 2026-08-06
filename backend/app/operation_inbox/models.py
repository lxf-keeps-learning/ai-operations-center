from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.operation_inbox.status import OP_AWAITING_REVIEW
from app.utils.timezone import now_local


class OperationMessage(Base):
    __tablename__ = "operation_message"
    __table_args__ = (
        Index("ix_operation_message_status_priority_created", "status", "priority", "created_at"),
        Index("ix_operation_message_assignee_status", "assignee_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    runtime_session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    report_chat_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=OP_AWAITING_REVIEW, index=True)
    assignee_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now_local, onupdate=now_local)
