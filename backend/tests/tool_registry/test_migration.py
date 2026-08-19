from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint


def _load_migration():
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260819_0004_create_tool_registry_tables.py"
    )
    spec = importlib.util.spec_from_file_location("tool_registry_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tool_registry_migration_creates_tables_constraints_and_indexes(monkeypatch) -> None:
    migration = _load_migration()

    created_tables: list[tuple] = []
    created_indexes: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(migration.op, "create_table", lambda *args: created_tables.append(args))
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda *args, **kwargs: created_indexes.append((args, kwargs)),
    )

    migration.upgrade()

    assert migration.revision == "20260819_0004"
    assert migration.down_revision == "20260806_0003"
    assert [table_args[0] for table_args in created_tables] == [
        "tool_definitions",
        "tool_versions",
        "tool_policies",
        "tool_call_audits",
    ]

    tool_versions_args = next(args for args in created_tables if args[0] == "tool_versions")
    assert any(
        isinstance(argument, UniqueConstraint) and argument.name == "uk_tool_version"
        for argument in tool_versions_args
    )

    tool_policies_args = next(args for args in created_tables if args[0] == "tool_policies")
    tool_call_audits_args = next(args for args in created_tables if args[0] == "tool_call_audits")
    assert sum(isinstance(argument, ForeignKeyConstraint) for argument in tool_policies_args) == 2
    assert sum(isinstance(argument, ForeignKeyConstraint) for argument in tool_call_audits_args) == 3

    index_names = {args[0]: (args[1], tuple(args[2]), kwargs) for args, kwargs in created_indexes}
    assert index_names["ix_tool_definitions_tool_key"][:2] == ("tool_definitions", ("tool_key",))
    assert index_names["ix_tool_definitions_capability"][:2] == ("tool_definitions", ("capability",))
    assert index_names["ix_tool_versions_tool_id_status"][:2] == ("tool_versions", ("tool_id", "status"))
    assert index_names["ix_tool_policies_scope"][:2] == (
        "tool_policies",
        ("tool_id", "version_id", "tenant_id", "role", "enabled"),
    )
    assert index_names["ix_tool_call_audits_trace_id"][:2] == ("tool_call_audits", ("trace_id",))


def test_tool_registry_migration_drops_indexes_before_tables(monkeypatch) -> None:
    migration = _load_migration()

    dropped_indexes: list[tuple[tuple, dict]] = []
    dropped_tables: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda *args, **kwargs: dropped_indexes.append((args, kwargs)),
    )
    monkeypatch.setattr(migration.op, "drop_table", lambda table_name: dropped_tables.append(table_name))

    migration.downgrade()

    assert dropped_tables == [
        "tool_call_audits",
        "tool_policies",
        "tool_versions",
        "tool_definitions",
    ]
    assert dropped_indexes[0][0][0] == "ix_tool_call_audits_tool_created_at"
    assert dropped_indexes[-1][0][0] == "ix_tool_definitions_enabled"
