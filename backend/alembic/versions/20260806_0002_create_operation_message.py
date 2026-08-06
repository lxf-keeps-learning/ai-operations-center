"""create operation message inbox table

Revision ID: 20260806_0002
Revises: 20260728_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260806_0002"
down_revision = "20260728_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_message",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("runtime_session_id", sa.String(length=64), nullable=False),
        sa.Column("report_id", sa.BigInteger(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operation_message_runtime_session_id",
        "operation_message",
        ["runtime_session_id"],
        unique=True,
    )
    op.create_index("ix_operation_message_report_id", "operation_message", ["report_id"])
    op.create_index("ix_operation_message_status", "operation_message", ["status"])
    op.create_index("ix_operation_message_assignee_id", "operation_message", ["assignee_id"])
    op.create_index("ix_operation_message_created_at", "operation_message", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_operation_message_created_at", table_name="operation_message")
    op.drop_index("ix_operation_message_assignee_id", table_name="operation_message")
    op.drop_index("ix_operation_message_status", table_name="operation_message")
    op.drop_index("ix_operation_message_report_id", table_name="operation_message")
    op.drop_index("ix_operation_message_runtime_session_id", table_name="operation_message")
    op.drop_table("operation_message")
