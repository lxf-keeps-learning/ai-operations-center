from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.operation_inbox.repository import OperationMessageRepository
from app.operation_inbox.status import OP_AWAITING_REVIEW, OP_REOPENED
from app.platform.repositories.overview_repository import RecentSessionRecord, OverviewRepository
from app.platform.schemas.overview_schema import OverviewMetrics, OverviewSession, PlatformOverviewResponse
from app.utils.timezone import now_local


class OverviewService:
    def __init__(
        self,
        repository: OverviewRepository | None = None,
        operation_message_repository: OperationMessageRepository | None = None,
    ) -> None:
        self.repository = repository or OverviewRepository()
        self.operation_message_repository = operation_message_repository or OperationMessageRepository()

    def get_overview(
        self,
        db: Session,
        *,
        now: datetime | None = None,
        recent_limit: int = 10,
    ) -> PlatformOverviewResponse:
        start, end = self._local_day_range(now or now_local())
        message_counts = self.operation_message_repository.count_by_status(db)
        metrics = OverviewMetrics(
            today_requests=self.repository.count_today_sessions(db, start, end),
            running_tasks=self.repository.count_running_sessions(db),
            pending_messages=(
                message_counts.get(OP_AWAITING_REVIEW, 0)
                + message_counts.get(OP_REOPENED, 0)
            ),
            failed_tasks=self.repository.count_today_failed_sessions(db, start, end),
            total_tokens=self.repository.sum_today_llm_tokens(db, start, end),
            agent_success_rate=self.repository.get_success_rate(db),
            average_response_ms=self.repository.get_average_response_ms(db),
        )
        return PlatformOverviewResponse(
            metrics=metrics,
            recent_sessions=[
                self._to_overview_session(record)
                for record in self.repository.list_recent_sessions(db, limit=recent_limit)
            ],
        )

    @staticmethod
    def _local_day_range(now: datetime) -> tuple[datetime, datetime]:
        if now.tzinfo is not None:
            now = now.astimezone(ZoneInfo(settings.app_timezone)).replace(tzinfo=None)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    @staticmethod
    def _to_overview_session(record: RecentSessionRecord) -> OverviewSession:
        context = record.session.context if isinstance(record.session.context, dict) else {}
        conversation = record.conversation
        return OverviewSession(
            id=record.session.id,
            conversation_id=record.session.conversation_id,
            title=(conversation.title if conversation and conversation.title else "Untitled conversation"),
            agent=record.session.task_type or "AI Agent",
            channel=(
                context.get("channel")
                or context.get("source")
                or (conversation.source if conversation else None)
                or "runtime"
            ),
            runs=record.runs,
            total_tokens=record.total_tokens,
            status=record.session.status,
            updated_at=record.session.updated_at,
        )
