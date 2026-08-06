"""extend operation message inbox persistence

Revision ID: 20260806_0003
Revises: 20260806_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0003"
down_revision = "20260806_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operation_message", sa.Column("report_chat_message_id", sa.String(length=64), nullable=True))
    op.add_column("operation_message", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_index(
        "ix_operation_message_status_priority_created",
        "operation_message",
        ["status", "priority", "created_at"],
    )
    op.create_index("ix_operation_message_assignee_status", "operation_message", ["assignee_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_operation_message_assignee_status", table_name="operation_message")
    op.drop_index("ix_operation_message_status_priority_created", table_name="operation_message")
    op.drop_column("operation_message", "retry_count")
    op.drop_column("operation_message", "report_chat_message_id")
