"""create evaluation center tables

Revision ID: 20260728_0002
Revises: 20260728_0001
Create Date: 2026-07-28 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0002"
down_revision: str | None = "20260728_0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "evaluation_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("prompt_key", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("graph_name", sa.String(128), nullable=True),
        sa.Column("node_name", sa.String(128), nullable=True),
        sa.Column("evaluator_key", sa.String(128), nullable=False),
        sa.Column("evaluator_type", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("violations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_eval_trace", "evaluation_result", ["trace_id"])
    op.create_index("idx_eval_prompt", "evaluation_result", ["prompt_key", "prompt_version"])
    op.create_index("idx_eval_evaluator", "evaluation_result", ["evaluator_key"])
    op.create_index("idx_eval_created", "evaluation_result", ["created_at"])

    op.create_table(
        "evaluation_metric",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_key", sa.String(128), nullable=False),
        sa.Column("prompt_version_id", sa.Integer(), nullable=True),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_metric_prompt", "evaluation_metric", ["prompt_key", "metric_name"])


def downgrade() -> None:
    op.drop_table("evaluation_metric")
    op.drop_table("evaluation_result")
