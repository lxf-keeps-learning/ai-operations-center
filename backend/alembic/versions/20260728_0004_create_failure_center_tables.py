"""create failure center tables

Revision ID: 20260728_0004
Revises: 20260728_0003
Create Date: 2026-07-28 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0004"
down_revision: str | None = "20260728_0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "failure_case",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("prompt_key", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("graph_name", sa.String(128), nullable=True),
        sa.Column("node_name", sa.String(128), nullable=True),
        sa.Column("failure_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("input", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("eval_result_ids", sa.JSON(), nullable=True),
        sa.Column("generated_case_id", sa.Integer(), nullable=True),
        sa.Column("eval_score", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_failure_trace", "failure_case", ["trace_id"])
    op.create_index("idx_failure_prompt", "failure_case", ["prompt_key"])
    op.create_index("idx_failure_type", "failure_case", ["failure_type"])
    op.create_index("idx_failure_status", "failure_case", ["status"])


def downgrade() -> None:
    op.drop_table("failure_case")
