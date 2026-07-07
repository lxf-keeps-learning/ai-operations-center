from typing import Any

from app.integrations.ioc.schema import IocApiResponse
from app.tool_center.core.exceptions import ToolException


def ensure_success(resp: IocApiResponse, code: str, message: str) -> None:
    """把 Client 失败响应转成 ToolException。

    BaseTool.run 会继续把 ToolException 包装成 ToolResult，避免异常穿透到 Graph。
    """

    if not resp.success:
        raise ToolException(code=code, message=message, detail={"reason": resp.error})


def result_metadata(resp: IocApiResponse) -> dict[str, Any]:
    """提取 Query Tool 通用 metadata。

    metadata 不参与业务结论，但能帮助 Graph 判断数据来源、总数和空数据分支。
    """

    total = resp.data.get("total", 0)
    return {
        "source": resp.source,
        "total": total,
        "empty": total == 0,
    }
