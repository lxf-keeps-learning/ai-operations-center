"""link report chat to runtime conversation and session

Revision ID: 20260710_0004
Revises: 786c07ec8ed1
Create Date: 2026-07-10 18:00:00.000000
"""

from collections.abc import Sequence
from collections import defaultdict
from datetime import datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_0004"
down_revision: str | Sequence[str] | None = "786c07ec8ed1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "report_chat_session",
        sa.Column("conversation_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_report_chat_session_conversation_id"),
        "report_chat_session",
        ["conversation_id"],
        unique=False,
    )
    op.add_column(
        "report_chat_message",
        sa.Column("runtime_session_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_report_chat_message_runtime_session_id"),
        "report_chat_message",
        ["runtime_session_id"],
        unique=False,
    )

    # 为历史报告会话补建统一 Conversation，随后回填历史消息的
    # Runtime Session 关联；列在迁移期间暂时允许为空。
    connection = op.get_bind()
    sessions = connection.execute(
        sa.text(
            "SELECT id, report_id, user_id, title, scene, status, created_at, updated_at "
            "FROM report_chat_session WHERE conversation_id IS NULL"
        )
    ).mappings()
    for session in sessions:
        conversation_id = f"conv_{datetime.now():%Y%m%d}_{uuid4().hex[:12]}"
        connection.execute(
            sa.text(
                "INSERT INTO ai_conversation "
                "(id, user_id, title, biz_type, source, status, metadata, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, 'report_chat', 'report_chat_agent', "
                "'active', NULL, :created_at, :updated_at)"
            ),
            {
                "id": conversation_id,
                "user_id": session["user_id"],
                "title": session["title"],
                "created_at": session["created_at"],
                "updated_at": session["updated_at"],
            },
        )
        connection.execute(
            sa.text(
                "UPDATE report_chat_session SET conversation_id=:conversation_id "
                "WHERE id=:session_id"
            ),
            {"conversation_id": conversation_id, "session_id": session["id"]},
        )

    # 将历史消息按 report session + trace 配对为统一 Runtime Session。
    # 同一 trace 被旧测试数据复用时，按角色内时间顺序逐一配对。
    session_rows = connection.execute(
        sa.text("SELECT id, conversation_id, user_id FROM report_chat_session")
    ).mappings()
    session_info = {row["id"]: row for row in session_rows}
    message_rows = connection.execute(
        sa.text(
            "SELECT id, session_id, trace_id, role, content, created_at "
            "FROM report_chat_message WHERE runtime_session_id IS NULL "
            "ORDER BY created_at, id"
        )
    ).mappings()
    grouped_messages: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(
        lambda: {"user": [], "assistant": []}
    )
    for message in message_rows:
        trace_key = message["trace_id"] or "__without_trace__"
        role = message["role"]
        if role in ("user", "assistant"):
            grouped_messages[(message["session_id"], trace_key)][role].append(dict(message))

    for (report_session_id, _trace_key), roles in grouped_messages.items():
        report_session = session_info[report_session_id]
        turn_count = max(len(roles["user"]), len(roles["assistant"]))
        for index in range(turn_count):
            user_message = roles["user"][index] if index < len(roles["user"]) else None
            assistant_message = (
                roles["assistant"][index] if index < len(roles["assistant"]) else None
            )
            runtime_session_id = f"sess_{datetime.now():%Y%m%d}_{uuid4().hex[:12]}"
            created_at = (
                user_message["created_at"]
                if user_message is not None
                else assistant_message["created_at"]
            )
            succeeded = user_message is not None and assistant_message is not None
            connection.execute(
                sa.text(
                    "INSERT INTO ai_session "
                    "(id, conversation_id, user_id, task_type, input_text, context, "
                    "output_text, status, error_message, started_at, finished_at, "
                    "expire_at, created_at, updated_at) "
                    "VALUES (:id, :conversation_id, :user_id, 'report_chat', :input_text, "
                    "NULL, :output_text, :status, :error_message, :started_at, "
                    ":finished_at, NULL, :created_at, :updated_at)"
                ),
                {
                    "id": runtime_session_id,
                    "conversation_id": report_session["conversation_id"],
                    "user_id": report_session["user_id"],
                    "input_text": user_message["content"] if user_message else "[历史记录缺少用户问题]",
                    "output_text": assistant_message["content"] if assistant_message else None,
                    "status": "success" if succeeded else "failed",
                    "error_message": None if succeeded else "历史报告问答消息不完整",
                    "started_at": created_at,
                    "finished_at": created_at,
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            )
            message_ids = [
                message["id"]
                for message in (user_message, assistant_message)
                if message is not None
            ]
            for message_id in message_ids:
                connection.execute(
                    sa.text(
                        "UPDATE report_chat_message SET runtime_session_id=:runtime_session_id "
                        "WHERE id=:message_id"
                    ),
                    {"runtime_session_id": runtime_session_id, "message_id": message_id},
                )

    op.alter_column(
        "report_chat_session",
        "conversation_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM ai_session WHERE id IN "
            "(SELECT runtime_session_id FROM report_chat_message "
            "WHERE runtime_session_id IS NOT NULL)"
        )
    )
    connection.execute(
        sa.text(
            "DELETE FROM ai_conversation WHERE id IN "
            "(SELECT conversation_id FROM report_chat_session "
            "WHERE conversation_id IS NOT NULL)"
        )
    )
    op.drop_index(
        op.f("ix_report_chat_message_runtime_session_id"),
        table_name="report_chat_message",
    )
    op.drop_column("report_chat_message", "runtime_session_id")
    op.drop_index(
        op.f("ix_report_chat_session_conversation_id"),
        table_name="report_chat_session",
    )
    op.drop_column("report_chat_session", "conversation_id")
