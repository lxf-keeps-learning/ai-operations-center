from app.tool_center.core.base_tool import BaseTool
from app.tool_center.core.exceptions import ToolNotFoundError


class ToolRegistry:
    """Tool 注册中心。

    Graph / Node 后续应通过 Registry 获取 Tool，而不是在流程节点里直接 new Tool。
    这样 Mock Client、真实 Client、权限包装、审计增强都可以集中在注册阶段处理。
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        # 同名 Tool 后注册会覆盖先注册，便于测试或本地环境替换 Mock/Real 实现。
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())
