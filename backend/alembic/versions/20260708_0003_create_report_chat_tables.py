"""create report chat tables

Revision ID: 20260708_0003
Revises: 42248f3f3230
Create Date: 2026-07-08 16:10:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260708_0003"
down_revision: str | Sequence[str] | None = "42248f3f3230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_chat_session",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scene", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_chat_session_created_at"),
        "report_chat_session",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_session_report_id"),
        "report_chat_session",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_session_scene"),
        "report_chat_session",
        ["scene"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_session_status"),
        "report_chat_session",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_session_user_id"),
        "report_chat_session",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "report_chat_message",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("question_scope", sa.String(length=64), nullable=True),
        sa.Column("answer_type", sa.String(length=64), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=True),
        sa.Column("query_scope", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_chat_message_created_at"),
        "report_chat_message",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_message_question_scope"),
        "report_chat_message",
        ["question_scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_message_report_id"),
        "report_chat_message",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_message_role"),
        "report_chat_message",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_message_session_id"),
        "report_chat_message",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_report_chat_message_trace_id"),
        "report_chat_message",
        ["trace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_report_chat_message_trace_id"), table_name="report_chat_message")
    op.drop_index(op.f("ix_report_chat_message_session_id"), table_name="report_chat_message")
    op.drop_index(op.f("ix_report_chat_message_role"), table_name="report_chat_message")
    op.drop_index(op.f("ix_report_chat_message_report_id"), table_name="report_chat_message")
    op.drop_index(op.f("ix_report_chat_message_question_scope"), table_name="report_chat_message")
    op.drop_index(op.f("ix_report_chat_message_created_at"), table_name="report_chat_message")
    op.drop_table("report_chat_message")

    op.drop_index(op.f("ix_report_chat_session_user_id"), table_name="report_chat_session")
    op.drop_index(op.f("ix_report_chat_session_status"), table_name="report_chat_session")
    op.drop_index(op.f("ix_report_chat_session_scene"), table_name="report_chat_session")
    op.drop_index(op.f("ix_report_chat_session_report_id"), table_name="report_chat_session")
    op.drop_index(op.f("ix_report_chat_session_created_at"), table_name="report_chat_session")
    op.drop_table("report_chat_session")
