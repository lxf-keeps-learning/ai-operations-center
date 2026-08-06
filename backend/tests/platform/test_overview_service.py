from collections.abc import Iterator
from datetime import datetime, timedelta
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["LANGGRAPH_POSTGRES_URL"] = ""
os.environ["MCP_ENABLED"] = "false"

from app.db.base import Base
from app.operation_inbox.models import OperationMessage
from app.operation_inbox.status import OP_AWAITING_REVIEW, OP_REOPENED
from app.runtime.models.conversation_model import AiConversation
from app.runtime.models.session_model import AiSession
from app.runtime.models.trace_model import AiTrace


FIXED_LOCAL_NOW = datetime(2026, 8, 6, 12, 0, 0)


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, expire_on_commit=False)
    with session_local() as db:
        yield db
    Base.metadata.drop_all(engine)


def _add_session(
    db: Session,
    *,
    session_id: str,
    conversation_id: str,
    created_at: datetime,
    updated_at: datetime,
    status: str,
    task_type: str | None = "report_chat",
    context: dict | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> AiSession:
    session = AiSession(
        id=session_id,
        conversation_id=conversation_id,
        user_id="operator",
        task_type=task_type,
        input_text="Analyze the operations report",
        context=context,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(session)
    return session


def _add_trace(
    db: Session,
    *,
    trace_id: str,
    session_id: str,
    span_type: str,
    total_tokens: int | None,
    created_at: datetime,
) -> None:
    db.add(AiTrace(
        id=trace_id,
        trace_id=trace_id,
        session_id=session_id,
        span_type=span_type,
        total_tokens=total_tokens,
        status="success",
        created_at=created_at,
    ))


def test_overview_aggregates_local_day_metrics_and_terminal_samples(db_session: Session) -> None:
    """Changing a day boundary, terminal denominator, or span filter must change this result."""
    day_start = FIXED_LOCAL_NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day = day_start + timedelta(days=1)
    db_session.add(AiConversation(
        id="conv_report",
        user_id="operator",
        title="Daily operations report",
        source="web",
        status="active",
    ))
    _add_session(
        db_session,
        session_id="before_day",
        conversation_id="conv_report",
        created_at=day_start - timedelta(microseconds=1),
        updated_at=day_start - timedelta(microseconds=1),
        status="success",
        started_at=day_start - timedelta(seconds=4),
        finished_at=day_start - timedelta(seconds=3),
    )
    _add_session(
        db_session,
        session_id="queued_today",
        conversation_id="conv_report",
        created_at=day_start,
        updated_at=FIXED_LOCAL_NOW,
        status="queued",
        context={"channel": "dashboard"},
    )
    _add_session(
        db_session,
        session_id="running_today",
        conversation_id="conv_report",
        created_at=FIXED_LOCAL_NOW,
        updated_at=FIXED_LOCAL_NOW + timedelta(minutes=1),
        status="running",
    )
    _add_session(
        db_session,
        session_id="failed_today",
        conversation_id="conv_report",
        created_at=next_day - timedelta(microseconds=1),
        updated_at=next_day - timedelta(microseconds=1),
        status="failed",
        started_at=FIXED_LOCAL_NOW,
        finished_at=FIXED_LOCAL_NOW + timedelta(seconds=2),
    )
    _add_session(
        db_session,
        session_id="after_day",
        conversation_id="conv_report",
        created_at=next_day,
        updated_at=next_day,
        status="success",
    )
    _add_trace(
        db_session,
        trace_id="trace_llm",
        session_id="queued_today",
        span_type="llm",
        total_tokens=120,
        created_at=FIXED_LOCAL_NOW,
    )
    _add_trace(
        db_session,
        trace_id="trace_null_llm",
        session_id="running_today",
        span_type="llm",
        total_tokens=None,
        created_at=FIXED_LOCAL_NOW,
    )
    _add_trace(
        db_session,
        trace_id="trace_graph",
        session_id="failed_today",
        span_type="graph",
        total_tokens=999,
        created_at=FIXED_LOCAL_NOW,
    )
    _add_trace(
        db_session,
        trace_id="trace_tomorrow",
        session_id="after_day",
        span_type="llm",
        total_tokens=777,
        created_at=next_day,
    )
    db_session.add_all([
        OperationMessage(id="message_pending", runtime_session_id="queued_today", status=OP_AWAITING_REVIEW),
        OperationMessage(id="message_reopened", runtime_session_id="running_today", status=OP_REOPENED),
    ])
    db_session.commit()

    from app.platform.services.overview_service import OverviewService

    result = OverviewService().get_overview(db_session, now=FIXED_LOCAL_NOW)

    assert result.metrics.model_dump() == {
        "today_requests": 3,
        "running_tasks": 2,
        "pending_messages": 2,
        "failed_tasks": 1,
        "total_tokens": 120,
        "agent_success_rate": pytest.approx(2 / 3),
        "average_response_ms": 1500.0,
    }


def test_overview_returns_newest_ten_sessions_with_joined_summary_fields(db_session: Session) -> None:
    """Removing sort, joins, per-conversation runs, or LLM token sums must fail this test."""
    db_session.add(AiConversation(
        id="conv_named",
        user_id="operator",
        title="Named conversation",
        source="web",
        status="active",
    ))
    for index in range(12):
        conversation_id = "conv_named" if index in {10, 11} else f"conv_{index}"
        if conversation_id != "conv_named":
            db_session.add(AiConversation(
                id=conversation_id,
                user_id="operator",
                title=None,
                source=None,
                status="active",
            ))
        session_id = f"session_{index:02d}"
        _add_session(
            db_session,
            session_id=session_id,
            conversation_id=conversation_id,
            created_at=FIXED_LOCAL_NOW,
            updated_at=FIXED_LOCAL_NOW + timedelta(minutes=index),
            status="success",
            task_type="report_chat" if index == 11 else None,
            context={"channel": "console"} if index == 11 else None,
        )
        _add_trace(
            db_session,
            trace_id=f"llm_{index:02d}",
            session_id=session_id,
            span_type="llm",
            total_tokens=index,
            created_at=FIXED_LOCAL_NOW,
        )
        _add_trace(
            db_session,
            trace_id=f"tool_{index:02d}",
            session_id=session_id,
            span_type="tool",
            total_tokens=500,
            created_at=FIXED_LOCAL_NOW,
        )
    db_session.commit()

    from app.platform.services.overview_service import OverviewService

    result = OverviewService().get_overview(db_session, now=FIXED_LOCAL_NOW)

    assert len(result.recent_sessions) == 10
    assert [item.id for item in result.recent_sessions] == [f"session_{index:02d}" for index in range(11, 1, -1)]
    assert result.recent_sessions[0].model_dump() == {
        "id": "session_11",
        "conversation_id": "conv_named",
        "title": "Named conversation",
        "agent": "report_chat",
        "channel": "console",
        "runs": 2,
        "total_tokens": 11,
        "status": "success",
        "updated_at": FIXED_LOCAL_NOW + timedelta(minutes=11),
    }
    unnamed_session = next(item for item in result.recent_sessions if item.id == "session_02")
    assert unnamed_session.title == "Untitled conversation"
