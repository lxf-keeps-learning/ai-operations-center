"""
页面上下文 — 当前用户所在页面的状态信息

生命周期：单次 HTTP 请求。
包含：pageCode（页面标识）、filters（当前筛选条件）、selectedObjectId（选中对象 ID）。
用于 Agent  Graph 理解用户当前所处的页面环境和操作上下文。
"""

from dataclasses import dataclass, field


@dataclass
class PageContext:
    page_code: str = ""
    filters: dict[str, object] = field(default_factory=dict)
    selected_object_id: str = ""

    def to_dict(self) -> dict:
        """转为驼峰命名字典，用于传递给 Agent Graph 或接口展示"""
        return {
            "pageCode": self.page_code,
            "filters": self.filters,
            "selectedObjectId": self.selected_object_id,
        }
