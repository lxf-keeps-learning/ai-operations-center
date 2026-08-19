"""harden tool registry governance

Revision ID: 20260819_0005
Revises: 20260819_0004
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0005"
down_revision = "20260819_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tool_definitions", sa.Column("created_by", sa.String(64), nullable=True))
    op.add_column("tool_definitions", sa.Column("updated_by", sa.String(64), nullable=True))

    op.add_column(
        "tool_versions",
        sa.Column("gray_percentage", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("tool_versions", sa.Column("retired_at", sa.DateTime(), nullable=True))
    op.add_column("tool_versions", sa.Column("retired_by", sa.String(64), nullable=True))
    op.add_column("tool_versions", sa.Column("created_by", sa.String(64), nullable=True))
    op.add_column("tool_versions", sa.Column("updated_by", sa.String(64), nullable=True))

    op.add_column(
        "tool_policies",
        sa.Column("active_scope_key", sa.String(64), nullable=True),
    )
    # Existing duplicate active scopes are resolved deterministically: newest id remains active.
    op.execute(
        sa.text(
            """
            UPDATE tool_policies AS older
            JOIN tool_policies AS newer
              ON older.tool_id = newer.tool_id
             AND older.version_id <=> newer.version_id
             AND older.tenant_id <=> newer.tenant_id
             AND older.role <=> newer.role
             AND older.id < newer.id
             AND older.enabled = 1
             AND newer.enabled = 1
            SET older.enabled = 0
            """
        )
    )
    # Length-prefixed components match policy_scope_key() without delimiter ambiguity.
    op.execute(
        sa.text(
            """
            UPDATE tool_policies
            SET active_scope_key = CASE
                WHEN enabled = 1 THEN SHA2(
                    CONCAT(
                        IF(
                            version_id IS NULL,
                            '#',
                            CONCAT(
                                CHAR_LENGTH(CAST(version_id AS CHAR)),
                                ':',
                                CAST(version_id AS CHAR)
                            )
                        ),
                        '|',
                        IF(
                            tenant_id IS NULL,
                            '#',
                            CONCAT(CHAR_LENGTH(tenant_id), ':', tenant_id)
                        ),
                        '|',
                        IF(
                            role IS NULL,
                            '#',
                            CONCAT(CHAR_LENGTH(role), ':', role)
                        )
                    ),
                    256
                )
                ELSE NULL
            END
            """
        )
    )
    op.create_index(
        "ux_tool_policies_active_scope",
        "tool_policies",
        ["tool_id", "active_scope_key"],
        unique=True,
    )
    op.create_check_constraint(
        "ck_tool_policies_active_scope_key",
        "tool_policies",
        "enabled = 0 OR active_scope_key IS NOT NULL",
    )

    op.add_column(
        "tool_call_audits",
        sa.Column("tool_key_snapshot", sa.String(128), nullable=True),
    )
    op.add_column(
        "tool_call_audits",
        sa.Column("capability_snapshot", sa.String(128), nullable=True),
    )
    op.add_column(
        "tool_call_audits",
        sa.Column("version_snapshot", sa.String(32), nullable=True),
    )
    op.add_column(
        "tool_call_audits",
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "tool_call_audits",
        sa.Column("confirmation_token_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ux_tool_call_audits_confirmation_token_hash",
        "tool_call_audits",
        ["confirmation_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_tool_call_audits_confirmation_token_hash",
        table_name="tool_call_audits",
    )
    op.drop_column("tool_call_audits", "confirmation_token_hash")
    op.drop_column("tool_call_audits", "policy_snapshot")
    op.drop_column("tool_call_audits", "version_snapshot")
    op.drop_column("tool_call_audits", "capability_snapshot")
    op.drop_column("tool_call_audits", "tool_key_snapshot")

    op.drop_constraint(
        "ck_tool_policies_active_scope_key",
        "tool_policies",
        type_="check",
    )
    op.drop_index("ux_tool_policies_active_scope", table_name="tool_policies")
    op.drop_column("tool_policies", "active_scope_key")

    op.drop_column("tool_versions", "updated_by")
    op.drop_column("tool_versions", "created_by")
    op.drop_column("tool_versions", "retired_by")
    op.drop_column("tool_versions", "retired_at")
    op.drop_column("tool_versions", "gray_percentage")

    op.drop_column("tool_definitions", "updated_by")
    op.drop_column("tool_definitions", "created_by")
