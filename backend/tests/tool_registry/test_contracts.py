from collections.abc import Mapping
from dataclasses import fields
from typing import get_type_hints

from app.tool_center.contracts import ToolContext
from app.tool_registry.contracts import ToolPolicyRecord, ToolVersionRecord


def test_tool_context_defaults_to_external() -> None:
    assert ToolContext().caller_type == "external"


def test_rollout_percentage_belongs_to_policies_not_versions() -> None:
    version_fields = {field.name for field in fields(ToolVersionRecord)}
    policy_fields = {field.name for field in fields(ToolPolicyRecord)}

    assert "gray_percentage" not in version_fields
    assert "gray_percentage" in policy_fields


def test_tool_version_record_schema_annotations_are_read_only_mappings() -> None:
    type_hints = get_type_hints(ToolVersionRecord)

    assert type_hints["input_schema"] == Mapping[str, object]
    assert type_hints["output_schema"] == Mapping[str, object]
