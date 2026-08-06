from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.runtime.models.conversation_model import AiConversation
from app.runtime.models.session_model import AiSession
from app.runtime.models.trace_model import AiTrace


TERMINAL_SESSION_STATUSES = ("success", "failed")


@dataclass(frozen=True)
class RecentSessionRecord:
    session: AiSession
    conversation: AiConversation | None
    runs: int
    total_tokens: int


class OverviewRepository:
    def count_today_sessions(self, db: Session, start: datetime, end: datetime) -> int:
        return int(db.scalar(
            select(func.count(AiSession.id)).where(AiSession.created_at >= start, AiSession.created_at < end)
        ) or 0)

    def count_running_sessions(self, db: Session) -> int:
        return int(db.scalar(
            select(func.count(AiSession.id)).where(AiSession.status.in_(("queued", "running")))
        ) or 0)

    def count_today_failed_sessions(self, db: Session, start: datetime, end: datetime) -> int:
        return int(db.scalar(
            select(func.count(AiSession.id)).where(
                AiSession.created_at >= start,
                AiSession.created_at < end,
                AiSession.status == "failed",
            )
        ) or 0)

    def sum_today_llm_tokens(self, db: Session, start: datetime, end: datetime) -> int:
        return int(db.scalar(
            select(func.coalesce(func.sum(AiTrace.total_tokens), 0)).where(
                AiTrace.created_at >= start,
                AiTrace.created_at < end,
                AiTrace.span_type == "llm",
            )
        ) or 0)

    def get_success_rate(self, db: Session) -> float:
        counts = dict(db.execute(
            select(AiSession.status, func.count(AiSession.id))
            .where(AiSession.status.in_(TERMINAL_SESSION_STATUSES))
            .group_by(AiSession.status)
        ).all())
        success_count = int(counts.get("success", 0))
        denominator = success_count + int(counts.get("failed", 0))
        return success_count / denominator if denominator else 0.0

    def get_average_response_ms(self, db: Session) -> float:
        samples = db.execute(
            select(AiSession.started_at, AiSession.finished_at).where(
                AiSession.status.in_(TERMINAL_SESSION_STATUSES),
                AiSession.started_at.is_not(None),
                AiSession.finished_at.is_not(None),
            )
        ).all()
        if not samples:
            return 0.0
        return sum(
            (finished_at - started_at).total_seconds() * 1000
            for started_at, finished_at in samples
        ) / len(samples)

    def list_recent_sessions(self, db: Session, *, limit: int = 10) -> list[RecentSessionRecord]:
        run_counts = (
            select(AiSession.conversation_id, func.count(AiSession.id).label("runs"))
            .group_by(AiSession.conversation_id)
            .subquery()
        )
        llm_tokens = (
            select(
                AiTrace.session_id,
                func.coalesce(func.sum(AiTrace.total_tokens), 0).label("total_tokens"),
            )
            .where(AiTrace.span_type == "llm")
            .group_by(AiTrace.session_id)
            .subquery()
        )
        rows = db.execute(
            select(
                AiSession,
                AiConversation,
                func.coalesce(run_counts.c.runs, 0),
                func.coalesce(llm_tokens.c.total_tokens, 0),
            )
            .outerjoin(AiConversation, AiConversation.id == AiSession.conversation_id)
            .outerjoin(run_counts, run_counts.c.conversation_id == AiSession.conversation_id)
            .outerjoin(llm_tokens, llm_tokens.c.session_id == AiSession.id)
            .order_by(AiSession.updated_at.desc(), AiSession.id.desc())
            .limit(limit)
        ).all()
        return [
            RecentSessionRecord(
                session=session,
                conversation=conversation,
                runs=int(runs),
                total_tokens=int(total_tokens),
            )
            for session, conversation, runs, total_tokens in rows
        ]
