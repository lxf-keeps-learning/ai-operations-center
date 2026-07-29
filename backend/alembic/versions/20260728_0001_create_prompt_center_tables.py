"""create prompt center tables

Revision ID: 20260728_0001
Revises: 20260711_0006_add_langgraph_runtime_prompt_facts
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0001"
down_revision: str | None = "20260711_0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_definition",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_key", sa.String(128), nullable=False),
        sa.Column("prompt_name", sa.String(255), nullable=False),
        sa.Column("business_scene", sa.String(128), nullable=True),
        sa.Column("graph_name", sa.String(128), nullable=True),
        sa.Column("node_name", sa.String(128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.String(64), nullable=True),
        sa.Column("current_version_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_key"),
    )
    op.create_index("idx_prompt_key", "prompt_definition", ["prompt_key"])
    op.create_index("idx_prompt_status", "prompt_definition", ["status"])
    op.create_index("idx_prompt_scene", "prompt_definition", ["business_scene"])
    op.create_index("idx_prompt_graph", "prompt_definition", ["graph_name"])

    op.create_table(
        "prompt_version",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("system_content", sa.Text(), nullable=True),
        sa.Column("business_role_content", sa.Text(), nullable=True),
        sa.Column("business_goal_content", sa.Text(), nullable=True),
        sa.Column("business_rules", sa.JSON(), nullable=True),
        sa.Column("output_requirement", sa.Text(), nullable=True),
        sa.Column("positive_examples", sa.JSON(), nullable=True),
        sa.Column("negative_examples", sa.JSON(), nullable=True),
        sa.Column("model_config", sa.JSON(), nullable=True),
        sa.Column("output_schema", sa.JSON(), nullable=True),
        sa.Column("langsmith_commit_hash", sa.String(128), nullable=True),
        sa.Column("langsmith_tag", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("change_reason", sa.String(500), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_id", "version", name="uk_prompt_version"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt_definition.id"]),
    )
    op.create_index("idx_version_prompt", "prompt_version", ["prompt_id"])
    op.create_index("idx_version_status", "prompt_version", ["status"])

    op.create_table(
        "prompt_variable",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("variable_key", sa.String(128), nullable=False),
        sa.Column("variable_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_type", sa.String(32), nullable=False, server_default="string"),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="graph_state"),
        sa.Column("source_path", sa.String(255), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("example_value", sa.Text(), nullable=True),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("editable", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt_definition.id"]),
    )
    op.create_index("idx_var_prompt", "prompt_variable", ["prompt_id"])

    op.create_table(
        "prompt_release",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("release_type", sa.String(32), nullable=False),
        sa.Column("traffic_ratio", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("approved_by", sa.String(64), nullable=True),
        sa.Column("released_by", sa.String(64), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=False),
        sa.Column("rollback_version_id", sa.Integer(), nullable=True),
        sa.Column("release_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt_definition.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["prompt_version.id"]),
    )
    op.create_index("idx_release_prompt", "prompt_release", ["prompt_id"])
    op.create_index("idx_release_env", "prompt_release", ["environment"])

    op.create_table(
        "prompt_test_case",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("case_name", sa.String(255), nullable=False),
        sa.Column("case_type", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("source_trace_id", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt_definition.id"]),
    )
    op.create_index("idx_case_prompt", "prompt_test_case", ["prompt_id"])

    op.create_table(
        "prompt_test_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(64), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("rendered_prompt", sa.Text(), nullable=True),
        sa.Column("raw_output", sa.Text(), nullable=True),
        sa.Column("structured_output", sa.JSON(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("latency", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt_definition.id"]),
        sa.ForeignKeyConstraint(["version_id"], ["prompt_version.id"]),
        sa.ForeignKeyConstraint(["test_case_id"], ["prompt_test_case.id"]),
    )
    op.create_index("idx_run_prompt", "prompt_test_run", ["prompt_id"])

    op.create_table(
        "prompt_evaluation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_run_id", sa.Integer(), nullable=False),
        sa.Column("evaluator_key", sa.String(128), nullable=False),
        sa.Column("evaluator_type", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("violations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["test_run_id"], ["prompt_test_run.id"]),
    )
    op.create_index("idx_eval_run", "prompt_evaluation", ["test_run_id"])

    op.create_table(
        "prompt_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_id", sa.Integer(), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("operator_id", sa.String(64), nullable=True),
        sa.Column("operator_name", sa.String(64), nullable=True),
        sa.Column("operator_ip", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prompt_id"], ["prompt_definition.id"]),
    )
    op.create_index("idx_audit_prompt", "prompt_audit_log", ["prompt_id"])
    op.create_index("idx_audit_action", "prompt_audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("prompt_audit_log")
    op.drop_table("prompt_evaluation")
    op.drop_table("prompt_test_run")
    op.drop_table("prompt_test_case")
    op.drop_table("prompt_release")
    op.drop_table("prompt_variable")
    op.drop_table("prompt_version")
    op.drop_table("prompt_definition")
