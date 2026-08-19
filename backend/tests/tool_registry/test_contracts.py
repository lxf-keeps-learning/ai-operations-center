from app.tool_center.contracts import ToolContext


def test_tool_context_defaults_to_external() -> None:
    assert ToolContext().caller_type == "external"
