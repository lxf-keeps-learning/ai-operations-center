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
        return {
            "traceId": self.trace_id,
            "requestTime": self.request_time.isoformat() if self.request_time else None,
            "clientIp": self.client_ip,
            "userAgent": self.user_agent,
            "method": self.method,
            "path": self.path,
        }
