from app.tool_center.base_tool import BaseTool
from app.tool_center.exceptions import ToolNotFoundError


class ExecutorCatalog:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, ref: str, tool: BaseTool) -> None:
        implementation_ref = self._normalize_ref(ref)
        self._tools[implementation_ref] = tool

    def get(self, ref: str) -> BaseTool:
        implementation_ref = self._normalize_ref(ref)
        if implementation_ref not in self._tools:
            raise ToolNotFoundError(implementation_ref)
        return self._tools[implementation_ref]

    def contains(self, ref: str) -> bool:
        implementation_ref = self._normalize_ref(ref)
        return implementation_ref in self._tools

    def clear(self) -> None:
        self._tools.clear()

    def _normalize_ref(self, ref: str) -> str:
        implementation_ref = ref.strip()
        if not implementation_ref:
            raise ValueError("implementation_ref must not be empty")
        return implementation_ref


executor_catalog = ExecutorCatalog()
