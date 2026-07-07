"""add prompt snapshot to ai_trace

Revision ID: 20260703_0002
Revises: 907e5e77381a
Create Date: 2026-07-03 18:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260703_0002"
down_revision: str | Sequence[str] | None = "907e5e77381a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_trace", sa.Column("prompt_snapshot", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_trace", "prompt_snapshot")
