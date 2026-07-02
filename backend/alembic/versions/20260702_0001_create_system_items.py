"""create system_items table

Revision ID: 20260702_0001
Revises:
Create Date: 2026-07-02
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260702_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(op.f("ix_system_items_id"), "system_items", ["id"], unique=False)
    op.create_index(op.f("ix_system_items_name"), "system_items", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_system_items_name"), table_name="system_items")
    op.drop_index(op.f("ix_system_items_id"), table_name="system_items")
    op.drop_table("system_items")
