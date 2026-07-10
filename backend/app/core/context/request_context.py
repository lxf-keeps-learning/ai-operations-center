"""
请求上下文 — 一次 HTTP 请求的元信息

生命周期：单次 HTTP 请求。
包含：traceId、请求时间、客户端 IP、User-Agent、请求方法与路径。
在 trace_middleware 中初始化，请求结束后自动清理。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RequestContext:
    trace_id: str = ""
    request_time: datetime | None = None
    client_ip: str = ""
    user_agent: str = ""
    method: str = ""
    path: str = ""

    def to_dict(self) -> dict:
        """转为驼峰命名字典，用于日志记录或接口展示"""
        return {
            "traceId": self.trace_id,
            "requestTime": self.request_time.isoformat() if self.request_time else None,
            "clientIp": self.client_ip,
            "userAgent": self.user_agent,
            "method": self.method,
            "path": self.path,
        }
