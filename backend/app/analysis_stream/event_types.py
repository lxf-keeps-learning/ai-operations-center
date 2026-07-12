"""SSE Streaming 事件类型与状态常量。"""

# 事件类型
EVENT_ANALYSIS_STARTED = "analysis_started"
EVENT_NODE_STARTED = "node_started"
EVENT_NODE_COMPLETED = "node_completed"
EVENT_NODE_FAILED = "node_failed"
EVENT_REPORT_COMPLETED = "report_completed"
EVENT_REPORT_DELTA = "report_delta"
EVENT_ANALYSIS_FAILED = "analysis_failed"
EVENT_HEARTBEAT = "heartbeat"
EVENT_STREAM_CLOSED = "stream_closed"

# 节点状态
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# P0 必须实现的事件列表
P0_EVENTS = {
    EVENT_ANALYSIS_STARTED,
    EVENT_NODE_STARTED,
    EVENT_NODE_COMPLETED,
    EVENT_NODE_FAILED,
    EVENT_REPORT_COMPLETED,
    EVENT_REPORT_DELTA,
    EVENT_ANALYSIS_FAILED,
    EVENT_STREAM_CLOSED,
}

# P1 可选事件列表
P1_EVENTS = {
    EVENT_HEARTBEAT,
}
