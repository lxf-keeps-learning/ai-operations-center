from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.operation_inbox.models import OperationMessage
from app.operation_inbox.status import (
    OP_AWAITING_REVIEW,
    OP_CLAIMED,
    OP_FAILED,
    OP_REOPENED,
    OP_RESOLVED,
)
from app.runtime.models.session_model import AiSession
from app.utils.ids import new_message_id
from app.utils.timezone import now_local


class OperationMessageRepository:
    def enqueue(
        self,
        db: Session,
        *,
        runtime_session_id: str,
        report_chat_message_id: str | None = None,
        report_id: int | None = None,
        priority: int = 0,
        status: str = OP_AWAITING_REVIEW,
    ) -> OperationMessage:
        existing = db.scalar(
            select(OperationMessage).where(OperationMessage.runtime_session_id == runtime_session_id)
        )
        if existing is not None:
            return existing

        message = OperationMessage(
            id=new_message_id(),
            runtime_session_id=runtime_session_id,
            report_chat_message_id=report_chat_message_id,
            report_id=report_id,
            priority=priority,
            status=status,
        )
        db.add(message)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            winner = db.scalar(
                select(OperationMessage).where(OperationMessage.runtime_session_id == runtime_session_id)
            )
            if winner is not None:
                return winner
            raise
        db.refresh(message)
        return message

    def list(
        self,
        db: Session,
        *,
        status: str | None = None,
        assignee_id: str | None = None,
        priority: int | None = None,
        report_id: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[OperationMessage]:
        self.reclaim_expired(db)
        stmt = select(OperationMessage)
        if status is not None:
            stmt = stmt.where(OperationMessage.status == status)
        if assignee_id is not None:
            stmt = stmt.where(OperationMessage.assignee_id == assignee_id)
        if priority is not None:
            stmt = stmt.where(OperationMessage.priority == priority)
        if report_id is not None:
            stmt = stmt.where(OperationMessage.report_id == report_id)
        stmt = stmt.order_by(OperationMessage.priority.desc(), OperationMessage.created_at.asc())
        return list(db.scalars(stmt.offset(offset).limit(limit)))

    def count_by_status(self, db: Session) -> dict[str, int]:
        self.reclaim_expired(db)
        rows = db.execute(
            select(OperationMessage.status, func.count(OperationMessage.id)).group_by(OperationMessage.status)
        ).all()
        return {status: count for status, count in rows}

    def get_by_id(self, db: Session, message_id: str) -> OperationMessage | None:
        self.reclaim_expired(db)
        return db.get(OperationMessage, message_id)

    def reclaim_expired(self, db: Session) -> int:
        """Release claimed messages whose lease has elapsed.

        The conditional update is atomic, so concurrent list/claim requests
        cannot reassign the same live lease. Expired work is reopened rather
        than treated as a fresh queue item, preserving the lifecycle history.
        """
        now = now_local()
        result = db.execute(
            update(OperationMessage)
            .where(
                OperationMessage.status == OP_CLAIMED,
                OperationMessage.lease_expires_at.is_not(None),
                OperationMessage.lease_expires_at <= now,
            )
            .values(
                status=OP_REOPENED,
                assignee_id=None,
                claimed_at=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        db.commit()
        return int(result.rowcount or 0)

    def sync_sessions(self, db: Session) -> None:
        """将已有运行记录纳入运营池，兼容队列 Worker 接入前的存量任务。"""
        existing = set(db.scalars(select(OperationMessage.runtime_session_id)).all())
        sessions = db.scalars(
            select(AiSession).where(AiSession.status.in_(["success", "failed", "running", "cancel_requested"]))
        ).all()
        for session in sessions:
            if session.id in existing:
                continue
            context = session.context if isinstance(session.context, dict) else {}
            report_id = context.get("report_id") or context.get("record_id")
            status = (
                OP_FAILED
                if session.status in {"failed", "cancel_requested"}
                else OP_AWAITING_REVIEW
                if session.status == "success"
                else "processing"
            )
            db.add(OperationMessage(
                id=new_message_id(),
                runtime_session_id=session.id,
                report_id=int(report_id) if isinstance(report_id, (int, str)) and str(report_id).isdigit() else None,
                priority=10 if session.task_type == "report_chat" else 0,
                status=status,
                error_message=session.error_message,
            ))
        db.commit()

    def list_with_sessions(
        self,
        db: Session,
        *,
        status: str | None,
        assignee_id: str | None,
        priority: int | None = None,
        report_id: int | None = None,
        limit: int,
        offset: int,
    ):
        self.reclaim_expired(db)
        stmt = select(OperationMessage, AiSession).outerjoin(
            AiSession,
            AiSession.id == OperationMessage.runtime_session_id,
        )
        if status == "mine":
            stmt = stmt.where(OperationMessage.assignee_id == assignee_id, OperationMessage.status == OP_CLAIMED)
        elif status == OP_CLAIMED:
            stmt = stmt.where(OperationMessage.status == OP_CLAIMED)
        elif status:
            stmt = stmt.where(OperationMessage.status == status)
        if priority is not None:
            stmt = stmt.where(OperationMessage.priority == priority)
        if report_id is not None:
            stmt = stmt.where(OperationMessage.report_id == report_id)
        stmt = stmt.order_by(OperationMessage.priority.desc(), OperationMessage.created_at.asc()).offset(offset).limit(limit)
        return list(db.execute(stmt).all())

    def get_with_session(self, db: Session, message_id: str):
        self.reclaim_expired(db)
        stmt = (
            select(OperationMessage, AiSession)
            .outerjoin(AiSession, AiSession.id == OperationMessage.runtime_session_id)
            .where(OperationMessage.id == message_id)
        )
        return db.execute(stmt).first()

    def claim(self, db: Session, message_id: str, operator_id: str, lease_minutes: int = 30) -> OperationMessage | None:
        self.reclaim_expired(db)
        now = now_local()
        result = db.execute(
            update(OperationMessage)
            .where(
                OperationMessage.id == message_id,
                OperationMessage.status.in_((OP_AWAITING_REVIEW, OP_REOPENED)),
                OperationMessage.assignee_id.is_(None),
            )
            .values(status=OP_CLAIMED, assignee_id=operator_id, claimed_at=now, lease_expires_at=now + timedelta(minutes=lease_minutes), updated_at=now)
        )
        if result.rowcount != 1:
            db.rollback()
            return None
        db.commit()
        return db.get(OperationMessage, message_id)

    def release(self, db: Session, message_id: str, operator_id: str) -> OperationMessage | None:
        self.reclaim_expired(db)
        record = db.get(OperationMessage, message_id)
        if record is None or record.status != OP_CLAIMED or record.assignee_id != operator_id:
            return None
        record.status = OP_AWAITING_REVIEW
        record.assignee_id = None
        record.claimed_at = None
        record.lease_expires_at = None
        db.commit()
        return record

    def resolve(self, db: Session, message_id: str, operator_id: str, note: str) -> OperationMessage | None:
        self.reclaim_expired(db)
        record = db.get(OperationMessage, message_id)
        if record is None or record.status != OP_CLAIMED or record.assignee_id != operator_id:
            return None
        record.status = OP_RESOLVED
        record.resolution_note = note.strip()[:4000] or None
        record.resolved_at = now_local()
        db.commit()
        return record

    def reopen(self, db: Session, message_id: str, operator_id: str) -> OperationMessage | None:
        record = db.get(OperationMessage, message_id)
        if not operator_id.strip() or record is None or record.status != OP_RESOLVED:
            return None
        record.status = OP_REOPENED
        record.assignee_id = None
        record.claimed_at = None
        record.lease_expires_at = None
        record.resolved_at = None
        db.commit()
        return record

    def retry(self, db: Session, message_id: str, operator_id: str) -> OperationMessage | None:
        record = db.get(OperationMessage, message_id)
        if not operator_id.strip() or record is None or record.status != OP_FAILED:
            return None
        record.status = OP_AWAITING_REVIEW
        record.assignee_id = None
        record.claimed_at = None
        record.lease_expires_at = None
        record.retry_count += 1
        db.commit()
        return record

    def summary(self, db: Session, *, assignee_id: str | None = None) -> dict[str, int]:
        rows = db.execute(select(OperationMessage.status, func.count(OperationMessage.id)).group_by(OperationMessage.status)).all()
        result = {
            OP_AWAITING_REVIEW: 0,
            OP_CLAIMED: 0,
            OP_RESOLVED: 0,
            OP_REOPENED: 0,
            OP_FAILED: 0,
            "processing": 0,
        }
        for status, count in rows:
            if status in result:
                result[status] = count
        result["mine"] = 0
        if assignee_id:
            result["mine"] = db.scalar(
                select(func.count(OperationMessage.id)).where(
                    OperationMessage.status == OP_CLAIMED,
                    OperationMessage.assignee_id == assignee_id,
                )
            ) or 0
        return result


OperationInboxRepository = OperationMessageRepository
operation_inbox_repo = OperationMessageRepository()
