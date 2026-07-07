import pytest

from app.tool_center.core.base_tool import BaseTool
from app.tool_center.core.exceptions import ToolNotFoundError
from app.tool_center.core.registry import ToolRegistry
from app.tool_center.core.schemas import BaseToolInput, Evidence


class MockTool(BaseTool):
    name = "mock_tool"
    description = "A mock tool for testing"

    def _execute(self, tool_input: BaseToolInput) -> tuple[list, list[Evidence]]:
        return [{"mock": True}], []


class AnotherTool(BaseTool):
    name = "another_tool"
    description = "Another tool for testing"

    def _execute(self, tool_input: BaseToolInput) -> tuple[list, list[Evidence]]:
        return [{"another": True}], []


class TestToolRegistry:
    def setup_method(self):
        self.registry = ToolRegistry()

    def test_register_tool(self):
        tool = MockTool()
        self.registry.register(tool)
        assert self.registry.list_tools() == ["mock_tool"]

    def test_get_tool_by_name(self):
        tool = MockTool()
        self.registry.register(tool)
        retrieved = self.registry.get("mock_tool")
        assert retrieved is tool
        assert retrieved.name == "mock_tool"

    def test_get_nonexistent_tool_raises(self):
        with pytest.raises(ToolNotFoundError) as exc_info:
            self.registry.get("nonexistent")
        assert "nonexistent" in str(exc_info.value)

    def test_list_tools_returns_all_names(self):
        self.registry.register(MockTool())
        self.registry.register(AnotherTool())
        names = self.registry.list_tools()
        assert "mock_tool" in names
        assert "another_tool" in names
        assert len(names) == 2

    def test_register_duplicate_overwrites(self):
        self.registry.register(MockTool())
        self.registry.register(MockTool())
        assert self.registry.list_tools() == ["mock_tool"]
