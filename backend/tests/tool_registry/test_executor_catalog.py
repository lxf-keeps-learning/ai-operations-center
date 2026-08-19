import pytest

from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, Evidence
from app.tool_registry.executor_catalog import ExecutorCatalog


class StubTool(BaseTool):
    name = "stub_tool"
    description = "Stub tool for executor catalog tests"

    def _execute(self, tool_input: BaseToolInput) -> tuple[list, list[Evidence]]:
        return [], []


def test_executor_catalog_binds_by_implementation_ref() -> None:
    catalog = ExecutorCatalog()
    tool = StubTool()

    catalog.register("builtin.stub", tool)

    assert catalog.get("builtin.stub") is tool


def test_executor_catalog_rejects_empty_ref() -> None:
    with pytest.raises(ValueError, match="implementation_ref"):
        ExecutorCatalog().register("", StubTool())
