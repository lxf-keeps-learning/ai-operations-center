"""create experiment center tables

Revision ID: 20260728_0003
Revises: 20260728_0002
Create Date: 2026-07-28 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0003"
down_revision: str | None = "20260728_0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_experiment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("source_version_id", sa.Integer(), nullable=False),
        sa.Column("target_version_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("winner_version", sa.String(32), nullable=True),
        sa.Column("total_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_case_ids", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt_definition.id"]),
        sa.ForeignKeyConstraint(["source_version_id"], ["prompt_version.id"]),
        sa.ForeignKeyConstraint(["target_version_id"], ["prompt_version.id"]),
    )
    op.create_index("idx_exp_prompt", "prompt_experiment", ["prompt_id"])
    op.create_index("idx_exp_status", "prompt_experiment", ["status"])

    op.create_table(
        "experiment_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["experiment_id"], ["prompt_experiment.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["prompt_version.id"]),
    )
    op.create_index("idx_exp_result_exp", "experiment_result", ["experiment_id"])
    op.create_index("idx_exp_result_version", "experiment_result", ["experiment_id", "version"])


def downgrade() -> None:
    op.drop_table("experiment_result")
    op.drop_table("prompt_experiment")
