from app.tool_center.core.base_tool import BaseTool
from app.tool_center.core.exceptions import ToolNotFoundError
from app.tool_center.core.registry import ToolRegistry

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
