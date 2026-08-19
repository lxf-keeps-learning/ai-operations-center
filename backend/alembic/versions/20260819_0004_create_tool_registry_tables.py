"""create tool registry tables

Revision ID: 20260819_0004
Revises: 20260806_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0004"
down_revision = "20260806_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool_key", sa.String(length=128), nullable=False),
        sa.Column("capability", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tool_type", sa.String(length=32), nullable=False),
        sa.Column("action_phase", sa.String(length=32), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "tool_type IN ('query', 'analysis', 'action') AND ("
            "(tool_type IN ('query', 'analysis') AND action_phase IS NULL) OR "
            "(tool_type = 'action' AND action_phase IS NOT NULL AND action_phase IN ('prepare', 'commit'))"
            ")",
            name="ck_tool_definitions_type_phase",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_definitions_tool_key", "tool_definitions", ["tool_key"], unique=True)
    op.create_index("ix_tool_definitions_capability", "tool_definitions", ["capability"], unique=True)
    op.create_index("ix_tool_definitions_enabled", "tool_definitions", ["enabled"])

    op.create_table(
        "tool_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("implementation_ref", sa.String(length=255), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_stable", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_tool_versions_status",
        ),
        sa.ForeignKeyConstraint(["tool_id"], ["tool_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_id", "version", name="uk_tool_version"),
    )
    op.create_index("ix_tool_versions_tool_id_status", "tool_versions", ["tool_id", "status"])
    op.create_index(
        "ix_tool_versions_tool_id_status_stable",
        "tool_versions",
        ["tool_id", "status", "is_stable"],
    )

    op.create_table(
        "tool_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False),
        sa.Column("gray_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tool_id"], ["tool_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["tool_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_policies_scope",
        "tool_policies",
        ["tool_id", "version_id", "tenant_id", "role", "enabled"],
    )
    op.create_index("ix_tool_policies_enabled", "tool_policies", ["enabled"])

    op.create_table(
        "tool_call_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("implementation_ref", sa.String(length=255), nullable=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("caller_type", sa.String(length=32), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("gray_bucket", sa.Integer(), nullable=True),
        sa.Column("selected_stable", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("argument_hash", sa.String(length=128), nullable=False),
        sa.Column("argument_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tool_id"], ["tool_definitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["version_id"], ["tool_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["policy_id"], ["tool_policies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_call_audits_trace_id", "tool_call_audits", ["trace_id"])
    op.create_index(
        "ix_tool_call_audits_tool_created_at",
        "tool_call_audits",
        ["tool_id", "created_at"],
    )
    op.create_index("ix_tool_call_audits_policy_id", "tool_call_audits", ["policy_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_call_audits_policy_id", table_name="tool_call_audits")
    op.drop_index("ix_tool_call_audits_tool_created_at", table_name="tool_call_audits")
    op.drop_index("ix_tool_call_audits_trace_id", table_name="tool_call_audits")
    op.drop_table("tool_call_audits")

    op.drop_index("ix_tool_policies_enabled", table_name="tool_policies")
    op.drop_index("ix_tool_policies_scope", table_name="tool_policies")
    op.drop_table("tool_policies")

    op.drop_index("ix_tool_versions_tool_id_status_stable", table_name="tool_versions")
    op.drop_index("ix_tool_versions_tool_id_status", table_name="tool_versions")
    op.drop_table("tool_versions")

    op.drop_index("ix_tool_definitions_enabled", table_name="tool_definitions")
    op.drop_index("ix_tool_definitions_capability", table_name="tool_definitions")
    op.drop_index("ix_tool_definitions_tool_key", table_name="tool_definitions")
    op.drop_table("tool_definitions")
