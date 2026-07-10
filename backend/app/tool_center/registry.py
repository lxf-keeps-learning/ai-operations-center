# 工具中心 - 注册中心模块
#
# 提供 ToolRegistry 类（内存字典注册中心）以及进程级全局实例，
# 上层模块（Graph / Node / API）通过统一接口注册、查询、列举 Tool。
#
# 当前为 Sprint3 内存注册表实现，后续可按需替换为持久化或分布式方案。
# 注册阶段可在此处统一注入 Mock/Real Client、权限校验、审计增强等横切关注点。

from app.tool_center.base_tool import BaseTool
from app.tool_center.exceptions import ToolNotFoundError


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


# 进程级全局 Registry。
#
# 当前 Sprint3 先用内存注册表满足本地开发和单元测试；后续如果要按租户、权限、
# 环境动态装配 Tool，可以保留下面这些函数作为统一入口，替换 registry 的构建方式。
registry = ToolRegistry()


def register_tool(tool: BaseTool) -> None:
    """注册单个 Tool，适合测试或按需装配场景。"""

    registry.register(tool)


def get_tool(name: str) -> BaseTool:
    """按名称获取 Tool；不存在时抛出 ToolNotFoundError。"""

    return registry.get(name)


def list_tools() -> list[str]:
    """列出当前进程已注册的 Tool 名称。"""

    return registry.list_tools()
